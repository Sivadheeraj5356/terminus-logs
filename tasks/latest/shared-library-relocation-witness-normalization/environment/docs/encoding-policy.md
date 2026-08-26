# Encoding policy — relocation witness formats

Standard ELF64 Rela witness rows (`Elf64_Rela`) are 24 bytes:

- `r_offset` (8 bytes): relocation target address.
- `r_info` (8 bytes): type in low 32 bits, symbol index in high 32 bits.
- `r_addend` (8 bytes): signed addend.

## Alpha (witness-ready)

Unmodified standard rows in `.rela.dyn` and `.rela.plt`.

## Beta (cipher-masked)

Each `r_info` is masked:

- `r_sym_masked = r_sym ^ 0x2A3B4C5D`
- `r_type_masked = r_type ^ 0x7E`
- `r_info_masked = (r_sym_masked << 32) | r_type_masked`

Relbind inverts the XOR mask in place.

## Gamma (envelope-packed)

Sections begin with an 8-byte header:

- `uint32_t magic = 0x474D524C` ("GMRL")
- `uint32_t num_entries`

Followed by `num_entries` packed records (16 bytes each):

- `uint32_t r_offset_lo` — low 32 bits of the final `r_offset` (zero-extended to 64 bits when expanded). This is an absolute relocation address, not a delta from the previous entry.
- `uint32_t sym_idx`
- `int32_t addend` — sign-extended to 64 bits
- `uint8_t type` plus 3 reserved bytes

Relbind expands each packed record to a standard 24-byte `Elf64_Rela` row using the absolute `r_offset_lo` value, writes rows sequentially from section offset zero, and zero-fills the remainder.
