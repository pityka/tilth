pub mod content;
pub mod glob;
pub mod rank;
pub mod symbol;

use std::fmt::Write;
use std::fs;
use std::path::Path;
use std::time::SystemTime;

use ignore::WalkBuilder;

use crate::cache::OutlineCache;
use crate::error::TilthError;
use crate::format;
use crate::read;
use crate::types::{FileType, Match, SearchResult};

// Directories that are always skipped — build artifacts, dependencies, VCS internals.
// We skip these explicitly instead of relying on .gitignore so that locally-relevant
// gitignored files (docs/, configs, generated code) are still searchable.
pub(crate) const SKIP_DIRS: &[&str] = &[
    ".git",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".pycache",
    "vendor",
    ".next",
    ".nuxt",
    "coverage",
    ".cache",
    ".tox",
    ".venv",
    ".eggs",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    ".turbo",
    ".parcel-cache",
    ".svelte-kit",
    "out",
    ".output",
    ".vercel",
    ".netlify",
    ".gradle",
    ".idea",
];

/// Build a parallel directory walker that searches ALL files except known junk directories.
/// Does NOT respect .gitignore — ensures gitignored but locally-relevant files are found.
pub(crate) fn walker(scope: &Path) -> ignore::WalkParallel {
    WalkBuilder::new(scope)
        .hidden(false)
        .git_ignore(false)
        .git_global(false)
        .git_exclude(false)
        .ignore(false)
        .parents(false)
        .filter_entry(|entry| {
            if entry.file_type().is_some_and(|ft| ft.is_dir()) {
                if let Some(name) = entry.file_name().to_str() {
                    return !SKIP_DIRS.contains(&name);
                }
            }
            true
        })
        .build_parallel()
}

/// Parse `/pattern/` regex syntax. Returns (pattern, `is_regex`).
fn parse_pattern(query: &str) -> (&str, bool) {
    if query.starts_with('/') && query.ends_with('/') && query.len() > 2 {
        (&query[1..query.len() - 1], true)
    } else {
        (query, false)
    }
}

/// Get `file_lines` estimate and mtime from metadata. One `stat()` per file.
pub(crate) fn file_metadata(path: &Path) -> (u32, SystemTime) {
    match std::fs::metadata(path) {
        Ok(meta) => {
            let mtime = meta.modified().unwrap_or(SystemTime::UNIX_EPOCH);
            let est_lines = (meta.len() / 40).max(1) as u32;
            (est_lines, mtime)
        }
        Err(_) => (0, SystemTime::UNIX_EPOCH),
    }
}

/// Dispatch search by query type.
pub fn search_symbol(
    query: &str,
    scope: &Path,
    cache: &OutlineCache,
) -> Result<String, TilthError> {
    let result = symbol::search(query, scope, None)?;
    format_search_result(&result, cache, 0)
}

pub fn search_symbol_expanded(
    query: &str,
    scope: &Path,
    cache: &OutlineCache,
    expand: usize,
    context: Option<&Path>,
) -> Result<String, TilthError> {
    let result = symbol::search(query, scope, context)?;
    format_search_result(&result, cache, expand)
}

pub fn search_content(
    query: &str,
    scope: &Path,
    cache: &OutlineCache,
) -> Result<String, TilthError> {
    let (pattern, is_regex) = parse_pattern(query);
    let result = content::search(pattern, scope, is_regex, None)?;
    format_search_result(&result, cache, 0)
}

pub fn search_content_expanded(
    query: &str,
    scope: &Path,
    cache: &OutlineCache,
    expand: usize,
    context: Option<&Path>,
) -> Result<String, TilthError> {
    let (pattern, is_regex) = parse_pattern(query);
    let result = content::search(pattern, scope, is_regex, context)?;
    format_search_result(&result, cache, expand)
}

/// Raw symbol search — returns structured result for programmatic inspection.
pub fn search_symbol_raw(query: &str, scope: &Path) -> Result<SearchResult, TilthError> {
    symbol::search(query, scope, None)
}

/// Raw content search — returns structured result for programmatic inspection.
pub fn search_content_raw(query: &str, scope: &Path) -> Result<SearchResult, TilthError> {
    let (pattern, is_regex) = parse_pattern(query);
    content::search(pattern, scope, is_regex, None)
}

/// Format a symbol search result (public for Fallthrough path in lib.rs).
pub fn format_symbol_result(
    result: &SearchResult,
    cache: &OutlineCache,
) -> Result<String, TilthError> {
    format_search_result(result, cache, 0)
}

/// Format a content search result (public for Fallthrough path in lib.rs).
pub fn format_content_result(
    result: &SearchResult,
    cache: &OutlineCache,
) -> Result<String, TilthError> {
    format_search_result(result, cache, 0)
}

pub fn search_glob(
    pattern: &str,
    scope: &Path,
    _cache: &OutlineCache,
) -> Result<String, TilthError> {
    let result = glob::search(pattern, scope)?;
    format_glob_result(&result, scope)
}

/// Format a symbol/content search result.
/// When an outline cache is available, wraps each match in the file's outline context.
/// When `expand > 0`, the top N matches inline actual code (def body or ±10 lines).
fn format_search_result(
    result: &SearchResult,
    cache: &OutlineCache,
    expand: usize,
) -> Result<String, TilthError> {
    let header = format::search_header(
        &result.query,
        &result.scope,
        result.matches.len(),
        result.definitions,
        result.usages,
    );

    let mut out = header;
    let mut expand_remaining = expand;

    for m in &result.matches {
        let kind = if m.is_definition {
            "definition"
        } else {
            "usage"
        };
        let _ = write!(out, "\n\n## {}:{} [{kind}]", m.path.display(), m.line);

        // Try to add outline context around the match
        if let Some(context) = outline_context_for_match(&m.path, m.line, cache) {
            out.push_str(&context);
        } else {
            let _ = write!(out, "\n→ [{}]   {}", m.line, m.text);
        }

        // Expand: inline actual code for top N matches
        if expand_remaining > 0 {
            if let Some(code) = expand_match(m) {
                out.push('\n');
                out.push_str(&code);
                expand_remaining -= 1;
            }
        }
    }

    if result.total_found > result.matches.len() {
        let omitted = result.total_found - result.matches.len();
        let _ = write!(
            out,
            "\n\n... and {omitted} more matches. Narrow with scope."
        );
    }

    Ok(out)
}

/// Inline the actual code for a match.
/// For definitions: use tree-sitter node range (`def_range`).
/// For usages: ±10 lines around the match.
fn expand_match(m: &Match) -> Option<String> {
    let (start, end) = m
        .def_range
        .unwrap_or((m.line.saturating_sub(10), m.line.saturating_add(10)));
    let content = fs::read_to_string(&m.path).ok()?;
    let lines: Vec<&str> = content.lines().collect();
    let total = lines.len() as u32;

    let start = start.max(1);
    let end = end.min(total);

    let mut out = String::new();
    let _ = write!(out, "\n```{}:{}-{}", m.path.display(), start, end);
    for i in start..=end {
        let idx = (i - 1) as usize;
        if idx < lines.len() {
            let _ = write!(out, "\n{:>4} │ {}", i, lines[idx]);
        }
    }
    out.push_str("\n```");
    Some(out)
}

/// Generate outline context for a search match: show nearby outline entries
/// with the matching entry highlighted using →.
fn outline_context_for_match(
    path: &std::path::Path,
    match_line: u32,
    cache: &OutlineCache,
) -> Option<String> {
    let file_type = read::detect_file_type(path);
    if !matches!(file_type, FileType::Code(_)) {
        return None;
    }

    // Get or compute the file's outline
    let meta = std::fs::metadata(path).ok()?;
    let mtime = meta.modified().unwrap_or(std::time::SystemTime::UNIX_EPOCH);
    let byte_len = meta.len();

    // Only compute outline context for reasonably sized files
    if byte_len > 500_000 {
        return None;
    }

    let outline_str = cache.get_or_compute(path, mtime, || {
        let content = std::fs::read_to_string(path).unwrap_or_default();
        let buf = content.as_bytes();
        read::outline::generate(path, file_type, &content, buf, false)
    });

    // Parse the outline to find entries near the match line
    let outline_lines: Vec<&str> = outline_str.lines().collect();
    if outline_lines.is_empty() {
        return None;
    }

    // Find which outline entries bracket the match line
    // Show entries with the closest one highlighted
    let mut context = String::new();
    let mut found_match = false;

    for line in &outline_lines {
        // Parse line range from outline entry format: [N-M] or [N]
        let is_match_entry = if let Some(range) = extract_line_range(line) {
            match_line >= range.0 && match_line <= range.1
        } else {
            false
        };

        if is_match_entry {
            let _ = write!(context, "\n→ {line}");
            found_match = true;
        } else {
            let _ = write!(context, "\n  {line}");
        }
    }

    if found_match {
        Some(context)
    } else {
        None
    }
}

/// Extract (`start_line`, `end_line`) from an outline entry like "[20-115]" or "[16]".
fn extract_line_range(line: &str) -> Option<(u32, u32)> {
    let trimmed = line.trim();
    if !trimmed.starts_with('[') {
        return None;
    }
    let end = trimmed.find(']')?;
    let range_str = &trimmed[1..end];
    if let Some((a, b)) = range_str.split_once('-') {
        let start: u32 = a.trim().parse().ok()?;
        // Handle import ranges like "[1-]"
        let end: u32 = if b.trim().is_empty() {
            start
        } else {
            b.trim().parse().ok()?
        };
        Some((start, end))
    } else {
        let n: u32 = range_str.trim().parse().ok()?;
        Some((n, n))
    }
}

/// Format glob search results (file list with previews).
fn format_glob_result(result: &glob::GlobResult, scope: &Path) -> Result<String, TilthError> {
    let header = format!(
        "# Glob: \"{}\" in {} — {} files",
        result.pattern,
        scope.display(),
        result.files.len()
    );

    let mut out = header;
    for file in &result.files {
        let _ = write!(out, "\n  {}", file.path.display());
        if let Some(ref preview) = file.preview {
            let _ = write!(out, "  ({preview})");
        }
    }

    if result.total_found > result.files.len() {
        let omitted = result.total_found - result.files.len();
        let _ = write!(out, "\n\n... and {omitted} more files. Narrow with scope.");
    }

    if result.files.is_empty() && !result.available_extensions.is_empty() {
        let _ = write!(
            out,
            "\n\nNo matches. Available extensions in scope: {}",
            result.available_extensions.join(", ")
        );
    }

    Ok(out)
}
