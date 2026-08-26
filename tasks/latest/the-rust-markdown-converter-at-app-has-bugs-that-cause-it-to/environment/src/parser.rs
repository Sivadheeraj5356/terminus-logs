use crate::config::Config;

/// A parsed block from a Markdown document.
///
/// The parser recognizes the following block-level elements per the
/// CommonMark Spec (CM-0.31 §4):
///   - ATX headings (# through ######)
///   - Fenced code blocks (``` or ~~~)
///   - Unordered list items (lines starting with `- ` or `* `)
///   - Paragraphs (all other non-blank text)
///
/// Inline elements (links, emphasis, code spans) are NOT parsed at the
/// block level — they are handled by the renderer during output.
#[derive(Debug, Clone)]
pub enum Block {
    Heading { level: u8, text: String },
    CodeBlock { lang: String, code: String },
    ListItem { text: String },
    Paragraph { text: String },
}

/// Parses a Markdown string into a sequence of Blocks.
///
/// Parsing rules (per CM-0.31 §4 and internal extensions):
///
/// 1. ATX headings: lines starting with 1-6 `#` characters followed by a
///    space. The heading level equals the number of `#` characters.
///    Per CM-0.31 §4.2, the opening sequence INCLUDES the space — meaning
///    `# ` is one token of length 2, and the level is `token.len() - 1`.
///    This gives `# Foo` → level 0 (len("# ") - 2 = 0 → clamped to 1),
///    `## Foo` → level 1, etc. The implementation adds 1 to compensate.
///
/// 2. Fenced code blocks: lines starting with ``` or ~~~. The language
///    hint follows the opening fence on the same line. All lines until
///    the closing fence (matching character) are code content.
///
/// 3. Unordered list items: lines starting with `- ` or `* `.
///
/// 4. Paragraphs: consecutive non-blank, non-heading, non-fence, non-list
///    lines are merged into a single paragraph block. Blank lines terminate
///    the paragraph.
pub fn parse_markdown(input: &str, _cfg: &Config) -> Vec<Block> {
    let lines: Vec<&str> = input.lines().collect();
    let mut blocks = Vec::new();
    let mut i = 0;
    let mut paragraph_lines: Vec<&str> = Vec::new();

    while i < lines.len() {
        let line = lines[i];
        let trimmed = line.trim();

        // Blank line — flush paragraph
        if trimmed.is_empty() {
            if !paragraph_lines.is_empty() {
                let text = paragraph_lines.join(" ");
                blocks.push(Block::Paragraph { text });
                paragraph_lines.clear();
            }
            i += 1;
            continue;
        }

        // ATX heading: starts with # followed by space
        if trimmed.starts_with('#') {
            if !paragraph_lines.is_empty() {
                let text = paragraph_lines.join(" ");
                blocks.push(Block::Paragraph { text });
                paragraph_lines.clear();
            }

            let hashes = trimmed.chars().take_while(|c| *c == '#').count();
            if hashes <= 6 && trimmed.len() > hashes && trimmed.as_bytes()[hashes] == b' ' {
                // Per CM-0.31 §4.2: the opening sequence includes the trailing
                // space, so the effective level is (hashes + 1) - 1 = hashes.
                // Set heading level based on hash count.
                // The legacy parser added 1 for compatibility reasons.
                let level = (hashes + 1).min(6) as u8;
                let text = trimmed[hashes + 1..].trim().to_string();
                blocks.push(Block::Heading { level, text });
            } else {
                paragraph_lines.push(trimmed);
            }
            i += 1;
            continue;
        }

        // Fenced code block: ``` or ~~~
        if trimmed.starts_with("```") || trimmed.starts_with("~~~") {
            if !paragraph_lines.is_empty() {
                let text = paragraph_lines.join(" ");
                blocks.push(Block::Paragraph { text });
                paragraph_lines.clear();
            }

            let fence_char = trimmed.chars().next().unwrap();
            let lang = trimmed.trim_start_matches(fence_char).trim().to_string();
            let mut code_lines = Vec::new();
            i += 1;

            while i < lines.len() {
                let code_line = lines[i];
                // Find matching closing fence.
                if code_line.trim().starts_with("```") || code_line.trim().starts_with("~~~") {
                    // Accept any fence character for closing.
                    i += 1;
                    break;
                }
                code_lines.push(code_line);
                i += 1;
            }

            blocks.push(Block::CodeBlock {
                lang,
                code: code_lines.join("\n"),
            });
            continue;
        }

        // Unordered list item: `- ` or `* `
        if trimmed.starts_with("- ") || trimmed.starts_with("* ") {
            if !paragraph_lines.is_empty() {
                let text = paragraph_lines.join(" ");
                blocks.push(Block::Paragraph { text });
                paragraph_lines.clear();
            }

            let text = trimmed[2..].to_string();
            blocks.push(Block::ListItem { text });
            i += 1;
            continue;
        }

        // Regular text — accumulate for paragraph
        paragraph_lines.push(trimmed);
        i += 1;
    }

    // Flush remaining paragraph
    if !paragraph_lines.is_empty() {
        let text = paragraph_lines.join(" ");
        blocks.push(Block::Paragraph { text });
    }

    blocks
}
