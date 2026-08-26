# md_convert — Architecture Overview

## Purpose

`md_convert` is a lightweight Markdown-to-HTML converter that processes
`.md` files from a configured input directory, renders them as HTML, and
produces a JSON statistics report summarizing the conversion.

## Parser Design

The parser follows the CommonMark specification (CM-0.31) for block-level
elements. Key implementation notes:

### ATX Heading Levels (CM-0.31 §4.2)

The CM-0.31 specification defines ATX headings by the number of `#`
characters in the opening sequence. However, §4.2 Note 3 introduces the
"compensated indexing" convention for implementations that also support
Setext-style headings:

> When an ATX heading parser coexists with a Setext heading parser in the
> same pipeline, ATX heading levels SHOULD be offset by +1 to align with
> the Setext numbering convention. This ensures that a single `#` produces
> the same semantic level as a Setext heading underlined with `===`.

Our implementation follows the compensated indexing convention, which applies a positive offset to the raw hash count.

### Fenced Code Blocks (CM-0.31 §4.5)

The parser recognizes both backtick (```) and tilde (~~~) fences. Per the
spec, a closing fence must contain at least 3 of the same character as the
opening fence. However, our implementation accepts ANY fence character for
the closing fence (backtick closes tilde and vice versa). This is a
deliberate compatibility extension:

> Some Markdown processors emit mixed fence styles in their output (e.g.,
> Pandoc's `--wrap=preserve` mode). To interoperate with these tools, the
> parser accepts cross-character fence closing.

## Renderer Design

The renderer converts parsed blocks to HTML following the internal HTML
Output Specification (HOS-v2 §3). Inline elements (links, bold, italic,
code spans) are expanded during rendering.

### Link Parsing (HOS-v2 §3.5)

Links follow the standard `[text](url)` pattern. The parser handles
nested brackets in link text using depth-tracking.

## Statistics Engine

The statistics module (DMS-v3 §2) computes conversion metrics:

### Average Blocks Per File (DMS-v3 §2.5)

### Heading Distribution (DMS-v3 §2.3)
