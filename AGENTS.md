# tilth

Code intelligence MCP server. Three core tools: search, read, files.

IMPORTANT: Use tilth tools for ALL code navigation. Never use Bash for grep, cat, find, or ls — tilth_search, tilth_read, and tilth_files replace these with better results.

Workflow: Start with tilth_search to find what you need. Always pass `context` (the file you're editing) — it boosts nearby results. With `expand` (default 2), you get code inlined, often eliminating a separate read. For cross-file tracing, pass multiple symbols comma-separated (e.g. query: "ServeHTTP, HandlersChain, Next") — each gets definitions from different files in one call. Expanded definitions include a `── calls ──` footer showing resolved callees — follow these instead of searching for each callee.

IMPORTANT: Expanded search results include full source code — do NOT re-read files already shown in search output. Answer from what you have rather than exploring further.

## tilth_read

Read a file. Small files → full content. Large files → structural outline (signatures, classes, imports).

- `path`: file path (single file)
- `paths`: array of file paths — read multiple files in one call, saves round-trips
- `section`: line range e.g. `"45-89"` or markdown heading e.g. `"## Architecture"` — returns only those lines (single `path` only)
- `full`: `true` to force full content on large files (single `path` only)
- `budget`: max response tokens

Use `path` for single file reads, `paths` for batch. Start with the outline. Use `section` to drill into what you need. For markdown, you can use heading names directly (e.g. `"## Architecture"`).

**Non-expanded definitions** (wavelet headers) show `path:start-end [definition]` with line range — use these ranges for direct section reads if you need to see the full source.

## tilth_search

Search code. Returns ranked results with structural context.

- `query` (required): symbol name, text, or `/regex/`. For symbol search, comma-separated names search multiple symbols in one call (max 5).
- `kind`: `"symbol"` (default) | `"content"` | `"regex"` | `"callers"`
- `expand`: number of top results to show with full source body (default 2). Shared across multi-symbol queries — each file expanded at most once.
- `context`: path of the file you're editing — boosts nearby results
- `scope`: directory to search within
- `budget`: max response tokens

Symbol search finds definitions first (tree-sitter AST), then usages. For cross-file tracing, pass multiple symbols comma-separated to get definitions from different files in one call. Use `kind: "callers"` to find all call sites of a symbol (structural matching, not text search). Use content search for strings/comments that aren't code symbols. Always pass `context` when editing a file.

**Expanded definitions** show a `── calls ──` footer with resolved callees (file:line-range + signature). Use this footer to navigate to callees instead of manually searching for each one. Re-expanding a previously shown definition shows `[shown earlier]` instead of the full body — session deduplication saves tokens.

## tilth_files

Find files by glob pattern. Returns paths + token estimates. Respects `.gitignore`.

- `pattern` (required): glob e.g. `"*.test.ts"`, `"src/**/*.rs"`
- `scope`: directory to search within
- `budget`: max response tokens

## tilth_edit

Hash-anchored file editing. Only available when installed with `--edit`.

When edit mode is enabled, `tilth_read` output includes content hashes on each line (`42:a3f| code`). Use these hashes as anchors for edits:

- `path` (required): file to edit
- `edits` (required): array of edit operations:
  - `start` (required): line anchor e.g. `"42:a3f"`
  - `end`: end anchor for range replacement (omit for single-line)
  - `content` (required): replacement text (empty string to delete)

If the file changed since the last read, hashes won't match and the edit is rejected with current content. Read the file again and retry.

For large files, use `tilth_read` with `section` to get hashlined content for the specific lines you need to edit.
