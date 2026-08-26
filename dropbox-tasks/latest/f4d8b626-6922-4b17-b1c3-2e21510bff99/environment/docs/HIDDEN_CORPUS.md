# Supplemental dive corpus

Some dive bundles are mounted only at check time and are not part of the bundled /app/data/dives tree during agent work. The tool must load any well formed bundle by path, not only bundled filenames.

## Bundle path resolution

When the TB3_DIVE_DIR environment variable is set to an absolute directory path, a bare bundle filename (single path component) resolves to TB3_DIVE_DIR joined with that filename.

When TB3_DIVE_DIR is not set, a bare bundle filename resolves under /app/data/dives.

Absolute bundle paths are used as given.

Relative paths with directory components resolve relative to the current working directory.

## Byte order mark

A bundle file may begin with a UTF-8 byte order mark. ingest-dive-log must strip a leading UTF-8 BOM before parsing the JSON body so that a BOM prefixed but otherwise valid bundle ingests exactly like the same bundle without a BOM.
