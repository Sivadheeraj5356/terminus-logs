# Disk image format

A disk image (`.dfi`) is a compiled container the `imgscan` reader inspects
before a filesystem would be mounted from it. All multi-byte integers are
**big-endian**. Counts, indices, modification-time deltas, flags, and lengths are
unsigned or signed **LEB128** varints; an inode's owner id is a fixed-width
unsigned 32-bit value.

## Superblock (8 bytes)

| offset | size | field        | notes                                  |
|-------:|-----:|--------------|----------------------------------------|
| 0      | 4    | magic        | ASCII `DFIM`                           |
| 4      | 1    | version      | format version, 1 or 2                 |
| 5      | 1    | region_count | number of region-table entries         |
| 6      | 2    | reserved     | zero                                   |

## Region table

Immediately after the superblock, `region_count` entries of **9 bytes** each:

| offset | size | field  |
|-------:|-----:|--------|
| 0      | 1    | kind   |
| 1      | 4    | offset |
| 5      | 4    | size   |

`offset` and `size` locate the region's bytes within the file. Region kinds:
`0` names, `1` volumes, `2` inodes, `3` links, `4` xattrs. A region of size 0 is
empty. The inodes region is required.

## names region (kind 0)

A pool of NUL-terminated byte strings. A volume's `label_off` is a byte offset
into this pool; the label runs from there to the next NUL.

## volumes region (kind 1)

A ULEB `volume_count` followed by that many volume descriptors. Each descriptor:

- `label_off` — u32, offset into the names pool
- `base_lba` — SLEB, a signed base logical block address
- `flags` — ULEB, a feature-flags word

## inodes region (kind 2)

A ULEB `inode_count` followed by that many inodes. Each inode:

- `uid` — u32, a fixed-width owner id
- `mtime_delta` — SLEB, a signed inter-inode modification-time delta
- `kind` — 1 byte: `0` file, `1` directory

A **file** inode then carries a ULEB `nbytes` and `nbytes` resident data bytes.

A **directory** inode then carries a ULEB `nchild` and `nchild` child inode
indices (each a ULEB index into the inode array). A directory is assembled from
the inodes it lists, so a child may itself be a directory.

## links region (kind 3)

A ULEB `link_count` followed by that many hardlink edges, each a ULEB `first`
inode index, a ULEB `second` inode index, and an SLEB `weight`. Both indices
refer to the inode array.

## xattrs region (kind 4)

A ULEB `xattr_count` followed by that many attributes, each a ULEB
`inode_index`, a ULEB `key`, a ULEB `value_len`, and then `value_len` value
bytes.

## Summary

For a well-formed file the reader prints a one-line JSON object with these keys:

- `format_version` — the superblock version
- `volumes_defined` — number of volume descriptors
- `inodes_defined` — number of inode entries
- `file_inodes`, `dir_inodes` — the split of the inodes by kind
- `hardlinks_parsed` — number of hardlink edges
- `xattrs_parsed` — number of attributes
- `data_bytes` — the total resident byte count reachable from inode 0, resolving
  a directory inode as the sum over the inodes it lists (a file inode
  contributes its own resident byte count). An inode may be listed more than
  once, and by more than one directory, and each listing contributes its
  footprint again, so the total is counted with multiplicity and can be as
  large as a 64-bit count.

## Subsystems

The reader reports a rejected file on stderr with a message naming the affected
subsystem, one of: `super`, `regtab`, `uleb`, `vol`, `inode`, `name`, `data`,
`child`, `link`, `xattr`.
