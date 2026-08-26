The Rust Markdown converter at `/app/` has bugs that cause it to produce incorrect HTML output and wrong statistics in `/app/output/report.json`. The tool reads `.md` files from `/app/input/`, converts each to an HTML file in `/app/output/`, and writes a JSON summary report.

The expected behavior for the parser and statistics generator is:
- **Headings**: The parser must strictly assign heading levels based on the exact number of `#` characters (from 1 to 6).
- **Code blocks**: Fenced code blocks must only be closed by a line that begins with a matching sequence of the exact same fence character (` ``` ` or `~~~`) that opened it.
- **Links**: The `link_count` metric must accurately accumulate all inline links found within the document (including both paragraphs and headings).
- **Statistics**: The `average_blocks_per_file` metric must accurately reflect a true floating-point average (rounded to 1 decimal place), avoiding truncation issues.
- **Heading Distribution**: The `heading_distribution` must accurately reflect the true, unshifted heading levels.

## Report Schema

The binary writes `/app/output/report.json` with the following top-level fields:
- `total_files`: Total number of `.md` files processed
- `total_lines`: Total source lines across all input files
- `heading_count`: Total ATX headings across all files
- `code_block_count`: Total fenced code blocks
- `list_item_count`: Total unordered list items
- `paragraph_count`: Total paragraphs
- `link_count`: Total inline links found in paragraphs and headings
- `average_blocks_per_file`: Float of `total_blocks / total_files`, rounded to 1 decimal place
- `heading_distribution`: A JSON object with integer counts for each heading level (e.g., `{"h1": 0, "h2": 5, "h3": 2, "h4": 0, "h5": 0, "h6": 0}`)

After fixing the source, rebuild and rerun the converter to regenerate the output.

Note that code comments and docstrings may themselves contain errors.
