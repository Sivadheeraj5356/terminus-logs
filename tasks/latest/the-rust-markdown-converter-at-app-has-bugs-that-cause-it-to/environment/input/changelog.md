# Release Notes

## Version 0.4.2

This release includes performance improvements and bug fixes.

### New Features

- Added support for [nested links](https://example.com/nested)
- Improved code block detection
- Added **heading distribution** to statistics report

### Bug Fixes

- Fixed memory leak in long-running conversion sessions
- Corrected UTF-8 handling for CJK characters

## Version 0.4.1

Minor maintenance release.

### Changes

- Updated serde dependency to 1.0.219
- Improved error messages for invalid Markdown

## Version 0.4.0

Major feature release.

### Highlights

- Complete rewrite of the parser module
- Added fenced code block support with language hints
- New statistics engine with heading distribution tracking

### Breaking Changes

- Config format changed from JSON to TOML
- Output directory structure simplified

#### Migration Guide

To migrate from 0.3.x:

- Replace `config.json` with `converter.toml`
- Update paths to use the new output layout
- See [migration guide](https://example.com/migrate) for details

### Known Issues

- Code blocks using mixed fence characters may interact unexpectedly
- Heading level display follows compensated indexing convention
