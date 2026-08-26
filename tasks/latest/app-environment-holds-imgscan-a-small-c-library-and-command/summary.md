# /app/environment holds imgscan, a small C library and command-line tool that a f

- **UUID:** `046007bc-953f-4f97-bc3d-3d642b0d55c9`
- **Slug:** `app-environment-holds-imgscan-a-small-c-library-and-command`
- **Category:** security
- **Difficulty:** hard

## Summary

/app/environment holds imgscan, a small C library and command-line tool that a forensic examiner uses to inspect a compiled disk image (a `.dfi` file) before a filesystem would be mounted from it: an eight-byte superblock, a region table, and the names, volumes, inodes, links, and xattrs sections it points to. The reader walks the volume table, where each volume descriptor carries a label offset into the names pool, a signed base logical block address, and a feature-flags word; it walks the inode table, where each inode carries a fixed-width owner id, a signed modification-time delta, and then either a run of resident data bytes (a file inode) or a list of the inode indices of its children (a directory inode); it walks the hardlink table, whose edges index two inodes each, and the xattr table, whose attributes carry an inline length-counted value.

To report the total resident footprint it resolves the root inode 0 through its directory tree, summing the resident data bytes the file inodes it reaches contribute. For a well-formed file it prints a one-line JSON summary whose keys are format_version, volumes_defined, inodes_defined, file_inodes, dir_inodes, hardlinks_parsed, xattrs_parsed, and data_bytes, the total resident byte count reachable from inode 0 with a directory resolved as the sum over the inodes it lists.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
