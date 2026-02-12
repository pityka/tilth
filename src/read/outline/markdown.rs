/// Markdown outline via memchr line scan — no markdown parser needed.
/// Find lines starting with `#`, extract heading level and text,
/// count code blocks per section. Shows line ranges for each heading.
pub fn outline(buf: &[u8], max_lines: usize) -> String {
    // First pass: collect all headings and count total lines
    let mut headings = Vec::new();
    let mut pos = 0;
    let mut line_num = 0u32;
    let mut code_block_count = 0u32;
    let mut in_code_block = false;

    while pos < buf.len() && headings.len() < max_lines {
        line_num += 1;

        // Find end of current line
        let line_end = memchr::memchr(b'\n', &buf[pos..]).map_or(buf.len(), |i| pos + i);

        let line = &buf[pos..line_end];

        // Track code blocks
        if line.starts_with(b"```") {
            if in_code_block {
                in_code_block = false;
            } else {
                in_code_block = true;
                code_block_count += 1;
            }
            pos = line_end + 1;
            continue;
        }

        if !in_code_block && !line.is_empty() && line[0] == b'#' {
            // Count heading level
            let level = line.iter().take_while(|&&b| b == b'#').count();
            if level <= 6 {
                let text_start = level + usize::from(line.get(level) == Some(&b' '));
                if let Ok(text) = std::str::from_utf8(&line[text_start..]) {
                    headings.push((line_num, level, text.to_string()));
                }
            }
        }

        pos = line_end + 1;
    }

    let total_lines = line_num;

    // Second pass: compute end lines for each heading and format output
    let mut entries = Vec::new();
    let num_headings = headings.len();

    for (i, (start_line, level, text)) in headings.iter().enumerate() {
        // Find next heading with same or higher level (lower level number)
        let end_line = if i + 1 < num_headings {
            // Look for next heading with level <= current level
            headings[i + 1..]
                .iter()
                .find(|(_, next_level, _)| next_level <= level)
                .map_or(total_lines, |(next_start, _, _)| next_start - 1)
        } else {
            // Last heading extends to end of file
            total_lines
        };

        let indent = "  ".repeat(level.saturating_sub(1));
        let hashes = "#".repeat(*level);
        let truncated = if text.len() > 80 {
            format!("{}...", crate::types::truncate_str(text, 77))
        } else {
            text.clone()
        };

        entries.push(format!(
            "[{start_line}-{end_line}] {indent}{hashes} {truncated}"
        ));
    }

    if code_block_count > 0 {
        entries.push(format!("\n({code_block_count} code blocks)"));
    }

    entries.join("\n")
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn basic_headings() {
        let input = b"# H1\nSome text\n## H2\nMore text\n";
        let result = outline(input, 100);
        let lines: Vec<&str> = result.lines().collect();

        assert_eq!(lines.len(), 2);
        // H1 extends to end of file (line 4) since no other H1
        assert_eq!(lines[0], "[1-4] # H1");
        // H2 also extends to end of file (line 4)
        assert_eq!(lines[1], "[3-4]   ## H2");
    }

    #[test]
    fn code_blocks_skipped() {
        let input = b"# Real Heading\n\n```\ncode\n```\n";
        let result = outline(input, 100);

        // Should only find the real heading, not any inside code block
        assert!(result.starts_with("[1-5] # Real Heading"));
        assert!(result.contains("(1 code blocks)"));
        assert!(!result.contains("Fake Heading"));
    }

    #[test]
    fn code_block_count() {
        let input = b"# Heading\n```\ncode\n```\n```\nmore\n```\n";
        let result = outline(input, 100);

        assert!(result.contains("(2 code blocks)"));
    }

    #[test]
    fn nested_heading_ranges() {
        let input = b"# A\ntext\n## B\ntext\n## C\ntext\n# D\ntext\n";
        let result = outline(input, 100);
        let lines: Vec<&str> = result.lines().collect();

        assert_eq!(lines.len(), 4);
        // A extends until D (line 7), so ends at line 6
        assert_eq!(lines[0], "[1-6] # A");
        // B extends until C (line 5), so ends at line 4
        assert_eq!(lines[1], "[3-4]   ## B");
        // C extends until D (line 7), so ends at line 6
        assert_eq!(lines[2], "[5-6]   ## C");
        // D extends to end of file (line 8)
        assert_eq!(lines[3], "[7-8] # D");
    }

    #[test]
    fn last_heading_to_eof() {
        let input = b"# Heading\nline 2\nline 3\nline 4\n";
        let result = outline(input, 100);

        // Heading should extend to line 4 (total line count)
        assert_eq!(result, "[1-4] # Heading");
    }

    #[test]
    fn empty_file() {
        let input = b"";
        let result = outline(input, 100);

        assert_eq!(result, "");
    }
}
