The config files use RFC-style CSV field quoting. Fields containing commas or
double quotes are enclosed in double quotes, and `""` decodes to one literal
double quote. Quoted fields do not contain record-ending characters in this
task. Readers accept LF or CRLF records, do not trim decoded values, and ignore
completely empty records. Lock rows are profile scoped and are the only
components allowed in a bundle. Filtered bundle CSVs preserve the header,
surviving source records, source order, and record-ending style; smoke specs are
copied byte-for-byte. Dependency `optional` values are case-sensitive: exactly
`yes`, `true`, and `1` mean true, and every other value means false.
