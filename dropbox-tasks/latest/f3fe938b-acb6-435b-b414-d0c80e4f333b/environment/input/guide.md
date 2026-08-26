# Getting Started

Welcome to the project documentation. This guide covers setup and usage.

## Installation

You can install the tool using the following methods:

- Download the binary from [releases](https://example.com/releases)
- Build from source using `cargo build --release`
- Use the Docker image

### System Requirements

The tool requires at least 2 GB of RAM and a modern 64-bit processor.

## Quick Start

Run the converter with:

```bash
md_convert --input ./docs --output ./html
```

This will process all `.md` files and generate HTML output.

## Configuration

Edit `/app/config/converter.toml` to customize behavior. See the
[configuration guide](https://example.com/config) for details.

### Advanced Options

For advanced usage, consult the **API reference** documentation.

## Troubleshooting

If you encounter issues:

- Check the log output for error messages
- Verify input files are valid Markdown
- Ensure output directory is writable
