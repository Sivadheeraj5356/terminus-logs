# dyeworks container layout

`dyeworks` reads a compiled dyeworks tree: a small wrapper that carries four sections
so a single-file reader can resolve the cross-section references the format
relies on. All multi-byte integers are big-endian. A conforming container is at
most 64 MiB; a file larger than that is malformed and rejected.

## Container header (8 bytes)

| offset | size | field      | meaning                              |
|-------:|-----:|------------|--------------------------------------|
| 0      | 4    | magic      | the bytes `DYEW` (`0x44594557` BE)   |
| 4      | 1    | version    | container version (1)                |
| 5      | 1    | nsections  | section count, always 4              |
| 6      | 2    | reserved   | recorded but not validated           |

## Section table (4 entries of 9 bytes, starting at offset 8)

| offset | size | field  | meaning                                          |
|-------:|-----:|--------|--------------------------------------------------|
| 0      | 1    | name   | 0 = dyeworksdefs, 1 = nodes, 2 = lots, 3 = strings |
| 1      | 4    | offset | byte offset of the section inside the file       |
| 5      | 4    | size   | byte length of the section                       |

The four named sections may appear in the file in any order after the table.

## varints (uleb128 / sleb128)

Type codes, counts, keys, form codes, and the `uleb` and `sleb` form values are
LEB128 varints: 7-bit groups least significant first, each group's high bit set
while more groups follow and clear on the last. A `uleb` holds an unsigned value
that fits in 64 bits; an `sleb` holds a signed value that fits a signed 64-bit
range. A varint is well-formed only when it both fits that width and spends no
more groups than that width needs. Three encodings are therefore malformed and
rejected: one whose groups run past the end of the section that holds it
(truncated); one that spends more than ten groups, including a value padded with
extra continuation groups that add no information (over-long); and one whose
groups carry a value outside the 64-bit range of its kind (overflow) — for a
`uleb` a tenth group that sets any bit above bit 63, and for an `sleb` a final
group that is not a clean sign extension of bit 63. A conforming file never
carries such an encoding.

## dyeworksdefs

A sequence of dyeworks-type declarations. The declaration list ends at a
declaration whose type code is zero. Each declaration is:

- `type_code` ULEB128 (nonzero)
- `type` ULEB128 (the dyeworks type: range, vat, dyeworks, skein, mordant, swatch)
- `has_children` one byte
- a list of `{key ULEB128, form ULEB128}` pairs ending with a `{0, 0}` pair

A container type (range, vat, dyeworks) carries children; a leaf type (skein,
mordant, swatch) does not. The `has_children` byte records that.

## nodes

A single unit. Its header is:

| field          | size | meaning                                             |
|----------------|-----:|-----------------------------------------------------|
| unit_length    | 4    | bytes of the unit after this field                  |
| version        | 2    | format version                                      |
| dyeworksdef_offset | 4   | offset of this unit's dyeworksdef in the dyeworksdef section |
| reserved       | 1    | reserved byte, recorded but not validated           |
| node_count     | 4    | number of node records the unit's table is sized for |

The unit header's reserved byte is recorded and reported but its value is not
restricted; the valid corpus carries a nonzero value there, so a file is not
turned away because that byte is not zero. The unit then holds the nodes, ending
where the unit length runs out. Each node
begins with a `type_code` ULEB128. A zero code is a null node that ends a
sibling chain. A nonzero code is looked up in the dyeworksdefs; for each
`{key, form}` pair in that declaration the node carries a value whose size the
form fixes. A node whose declaration sets `has_children` is followed by its own
sibling chain of child nodes, ending with a null node; a child chain that reaches
the unit end without that closing null node is malformed. A container node may
carry nested container nodes, so a sibling chain may nest several levels deep. The
format bounds this nesting at 256 levels: a well-formed tree never nests deeper
than 256 levels and must keep parsing, while a tree nested beyond 256 levels is
malformed and rejected.

| form            | code | value                                            |
|-----------------|-----:|--------------------------------------------------|
| data1           | 0x01 | 1 byte                                           |
| data2           | 0x02 | 2 bytes                                          |
| data4           | 0x03 | 4 bytes                                          |
| data8           | 0x04 | 8 bytes                                          |
| uleb            | 0x05 | unsigned ULEB128                                 |
| sleb            | 0x06 | signed LEB128                                    |
| str             | 0x07 | 4-byte offset into the strings section           |
| string          | 0x08 | inline bytes up to a terminating NUL             |
| block1          | 0x09 | 1-byte length followed by that many bytes        |
| block2          | 0x0a | 2-byte length followed by that many bytes        |
| block4          | 0x0b | 4-byte length followed by that many bytes        |
| flag            | 0x0c | no bytes, a presence flag                        |
| indirect        | 0x10 | a ULEB128 naming the actual form, then the value in that form |
| lot            | 0x11 | 4-byte index into the lots table                |

A param whose form is `indirect` does not fix the value's encoding in the
declaration. Instead the value begins with a ULEB128 that names the form to use,
and the value follows encoded in that named form. The named form must be a
concrete form such as `str` or `data4`, and such a param parses like the direct
form it names; an indirect value that names `indirect` again is malformed and
rejected, so an indirect value resolves in a single step. The other forms above
are read directly as their row describes.

## lots

An array of four-byte lot ids. A `lot` param carries a four-byte index that
selects one entry by position.

## strings

A run of NUL-terminated strings indexed by a `str` offset.

## Output

For a well-formed file the reader prints a one-line JSON summary naming the
format version, the number of dyeworksdef declarations, the number of non-null
nodes, the number of lot references resolved, the number of indirect forms
resolved, and the type of the root node. A malformed file is rejected with a
nonzero exit and a short stderr message naming the subsystem that caught it.
