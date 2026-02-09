/// Markdown outline via memchr line scan — no markdown parser needed.
/// Find lines starting with `#`, extract heading level and text,
/// count code blocks per section. Tracks actual line numbers.
pub fn outline(buf: &[u8], max_lines: usize) -> String {
    let mut entries = Vec::new();
    let mut pos = 0;
    let mut line_num = 0u32;
    let mut code_block_count = 0u32;
    let mut in_code_block = false;

    while pos < buf.len() && entries.len() < max_lines {
        line_num += 1;

        // Find end of current line
        let line_end = memchr::memchr(b'\n', &buf[pos..])
            .map_or(buf.len(), |i| pos + i);

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
                    let indent = "  ".repeat(level.saturating_sub(1));
                    let truncated = if text.len() > 80 {
                        format!("{}...", crate::types::truncate_str(text, 77))
                    } else {
                        text.to_string()
                    };
                    entries.push(format!("[{line_num}] {indent}{truncated}"));
                }
            }
        }

        pos = line_end + 1;
    }

    if code_block_count > 0 {
        entries.push(format!("\n({code_block_count} code blocks)"));
    }

    entries.join("\n")
}
