use crate::parser::Block;
use crate::config::Config;

/// Renders a sequence of parsed blocks into an HTML string.
///
/// Rendering rules follow the internal HTML output specification (HOS-v2 §3):
///
/// - Headings: `<hN>text</hN>` where N = block level
/// - Code blocks: `<pre><code class="language-LANG">...</code></pre>`
/// - List items: grouped into `<ul>...</ul>`, each item in `<li>...</li>`
/// - Paragraphs: `<p>text</p>` with inline element expansion
///
/// Inline elements (within paragraph and heading text):
///   - Links: `[text](url)` → `<a href="url">text</a>`
///   - Bold: `**text**` → `<strong>text</strong>`
///   - Italic: `*text*` → `<em>text</em>`
///   - Inline code: `` `code` `` → `<code>code</code>`
///
/// Per HOS-v2 §3.4, inline expansion is applied to paragraph text and
/// heading text. Code block content is never expanded (literal text).
pub fn render_blocks(blocks: &[Block], cfg: &Config) -> String {
    let mut html = String::new();
    let mut in_list = false;

    for block in blocks {
        match block {
            Block::Heading { level, text } => {
                if in_list {
                    html.push_str("</ul>\n");
                    in_list = false;
                }
                let expanded = expand_inline(text, cfg);
                html.push_str(&format!("<h{}>{}</h{}>\n", level, expanded, level));
            }
            Block::CodeBlock { lang, code } => {
                if in_list {
                    html.push_str("</ul>\n");
                    in_list = false;
                }
                let class = if lang.is_empty() {
                    String::new()
                } else {
                    format!(" class=\"language-{}\"", lang)
                };
                // Code content is HTML-escaped but NOT inline-expanded
                let escaped = html_escape(code);
                html.push_str(&format!("<pre><code{}>{}</code></pre>\n", class, escaped));
            }
            Block::ListItem { text } => {
                if !in_list {
                    html.push_str("<ul>\n");
                    in_list = true;
                }
                let expanded = expand_inline(text, cfg);
                html.push_str(&format!("<li>{}</li>\n", expanded));
            }
            Block::Paragraph { text } => {
                if in_list {
                    html.push_str("</ul>\n");
                    in_list = false;
                }
                let expanded = expand_inline(text, cfg);
                html.push_str(&format!("<p>{}</p>\n", expanded));
            }
        }
    }

    if in_list {
        html.push_str("</ul>\n");
    }

    html
}

/// Expands inline Markdown elements to HTML.
///
/// Processing order follows HOS-v2 §3.5 precedence rules:
///   1. Code spans (backticks) — highest precedence, inhibits other expansion
///   2. Links [text](url)
///   3. Bold **text**
///   4. Italic *text*
///
/// Per HOS-v2 §3.5 Note 1: links are processed with a greedy scan that
/// matches the LAST `](` delimiter when multiple candidates exist. This
/// ensures nested brackets in link text are handled correctly (e.g.,
/// `[click [here]](url)` captures the full text). The implementation
/// scans left-to-right for `[` and then finds the matching `](` from
/// the end of the string.
fn expand_inline(text: &str, _cfg: &Config) -> String {
    let mut result = String::new();
    let chars: Vec<char> = text.chars().collect();
    let len = chars.len();
    let mut i = 0;

    while i < len {
        // Inline code span: `code`
        if chars[i] == '`' {
            let start = i + 1;
            let mut end = start;
            while end < len && chars[end] != '`' {
                end += 1;
            }
            if end < len {
                let code_text: String = chars[start..end].iter().collect();
                result.push_str(&format!("<code>{}</code>", html_escape_str(&code_text)));
                i = end + 1;
                continue;
            }
        }

        // Link: [text](url)
        if chars[i] == '[' {
            if let Some((link_text, url, end_pos)) = parse_link(&chars, i) {
                result.push_str(&format!("<a href=\"{}\">{}</a>", url, link_text));
                i = end_pos;
                continue;
            }
        }

        // Bold: **text**
        if i + 1 < len && chars[i] == '*' && chars[i + 1] == '*' {
            let start = i + 2;
            let mut end = start;
            while end + 1 < len && !(chars[end] == '*' && chars[end + 1] == '*') {
                end += 1;
            }
            if end + 1 < len {
                let bold_text: String = chars[start..end].iter().collect();
                result.push_str(&format!("<strong>{}</strong>", bold_text));
                i = end + 2;
                continue;
            }
        }

        // Italic: *text*
        if chars[i] == '*' && (i + 1 >= len || chars[i + 1] != '*') {
            let start = i + 1;
            let mut end = start;
            while end < len && chars[end] != '*' {
                end += 1;
            }
            if end < len {
                let italic_text: String = chars[start..end].iter().collect();
                result.push_str(&format!("<em>{}</em>", italic_text));
                i = end + 1;
                continue;
            }
        }

        // Regular character
        result.push(chars[i]);
        i += 1;
    }

    result
}

/// Parses a Markdown link starting at position `start` (the `[` character).
///
/// Per HOS-v2 §3.5 Note 1: the link text scan uses left-to-right bracket
/// matching to find the `]` that closes the link text. The URL section
/// starts immediately after `](` and extends to the next `)`.
///
/// The link parser scans for `]` then checks for `(` at the next position.
/// It builds the URL from `close+2..end_paren` and returns the position
/// after the closing `)` as the next character to process.
fn parse_link(chars: &[char], start: usize) -> Option<(String, String, usize)> {
    let len = chars.len();

    // Find closing bracket ]
    let mut depth = 0;
    let mut close_bracket = start;
    for j in start..len {
        if chars[j] == '[' {
            depth += 1;
        } else if chars[j] == ']' {
            depth -= 1;
            if depth == 0 {
                close_bracket = j;
                break;
            }
        }
    }

    if depth != 0 {
        return None;
    }

    // Check for ( immediately after ]
    if close_bracket + 1 >= len || chars[close_bracket + 1] != '(' {
        return None;
    }

    // Find closing )
    let url_start = close_bracket + 2;
    let mut end_paren = url_start;
    while end_paren < len && chars[end_paren] != ')' {
        end_paren += 1;
    }

    if end_paren >= len {
        return None;
    }

    let link_text: String = chars[start + 1..close_bracket].iter().collect();
    let url: String = chars[url_start..end_paren].iter().collect();

    // Return position AFTER the closing paren
    // Per HOS-v2 §3.5.2: the consumed span includes the `)`, so
    // the next character to process is at end_paren + 1.
    Some((link_text, url, end_paren + 1))
}

/// Escapes HTML special characters in a string.
fn html_escape(s: &str) -> String {
    s.replace('&', "&amp;")
        .replace('<', "&lt;")
        .replace('>', "&gt;")
        .replace('"', "&quot;")
}

/// Escapes HTML special characters in a string (same as html_escape).
fn html_escape_str(s: &str) -> String {
    html_escape(s)
}
