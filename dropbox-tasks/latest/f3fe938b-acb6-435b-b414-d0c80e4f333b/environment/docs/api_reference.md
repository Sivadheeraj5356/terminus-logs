# md_convert — API Reference

## Module: `parser`

### `parse_markdown(input: &str, cfg: &Config) -> Vec<Block>`

Parses a Markdown string into block-level elements.

**Block types:**
- `Heading { level: u8, text: String }` — ATX heading with compensated
  level (raw `#` count + 1, clamped to 1..6)
- `CodeBlock { lang: String, code: String }` — fenced code block (```,
  ~~~); closing fence accepts any fence character
- `ListItem { text: String }` — unordered list item (`- ` or `* `)
- `Paragraph { text: String }` — merged consecutive text lines

**Heading level formula:**
```
level = apply_compensated_offset(hashes)
```
where `hashes` = count of `#` characters in the opening sequence.

---

## Module: `renderer`

### `render_blocks(blocks: &[Block], cfg: &Config) -> String`

Renders parsed blocks to an HTML string.

**Output mapping:**
| Block Type | HTML |
|-----------|------|
| Heading(N, text) | `<hN>expanded(text)</hN>` |
| CodeBlock(lang, code) | `<pre><code class="language-LANG">escaped(code)</code></pre>` |
| ListItem(text) | `<li>expanded(text)</li>` (wrapped in `<ul>`) |
| Paragraph(text) | `<p>expanded(text)</p>` |

**Inline expansion:**
- `[text](url)` → `<a href="url">text</a>`
- `**text**` → `<strong>text</strong>`
- `*text*` → `<em>text</em>`
- `` `code` `` → `<code>code</code>`

---

## Module: `stats`

### `compute_stats(file_blocks: &[&[Block]], total_lines: u64, cfg: &Config) -> ConversionReport`

Computes conversion statistics.

**average_blocks_per_file formula:**
```
average = compute_average_integer_rounded(total_blocks, total_files) as f64
```

**heading_distribution:** Maps computed heading levels (after offset) to
counts. `h1` through `h6`.

---

## Module: `config`

### `load_config(path: &str) -> Config`

Loads key-value configuration. Defaults:

| Key | Default |
|-----|---------|
| `input_dir` | `/app/input` |
| `output_dir` | `/app/output` |
| `report_path` | `/app/output/report.json` |
