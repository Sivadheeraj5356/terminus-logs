# FITS-LITE 2 format

FITS-LITE 2 files are newline-oriented text. The first line is `FITS-LITE 2`.
Each HDU starts with `HDU NAME` and ends with `END_HDU`. Matrix HDUs include a
`DATA` line followed by whitespace-separated numeric rows.

The recovery bundle publishes `PRIMARY_IMAGE`, `COVERAGE`, `CHECKPOINT`,
`PROVENANCE`, and `CHECKSUMS`. `CHECKSUMS` contains FNV64 hexadecimal checksums
for the final text of the first four HDUs, including the `HDU` and `END_HDU`
lines and a newline after every line.
