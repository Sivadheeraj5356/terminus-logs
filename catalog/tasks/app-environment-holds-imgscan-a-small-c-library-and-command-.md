# /app/environment holds imgscan, a small C library and command-line tool that a f

Submission: `046007bc-953f-4f97-bc3d-3d642b0d55c9`  
Slug: `app-environment-holds-imgscan-a-small-c-library-and-command-`  
Latest archive: `046007bc-953f-4f97-bc3d-3d642b0d55c9_submission_2026-07-17T16_16_44.223Z.zip`  
Revisions in Dropbox: 3

## Task summary

/app/environment holds imgscan, a small C library and command-line tool that a forensic examiner uses to inspect a compiled disk image (a `.dfi` file) before a filesystem would be mounted from it: an eight-byte superblock, a region table, and the names, volumes, inodes, links, and xattrs sections it points to. The reader walks the volume table, where each volume descriptor carries a label offset into the names pool, a signed base logical block address, and a feature-flags word; it walks the inode table, where each inode carries a fixed-width owner id, a signed modification-time delta, and then either a run of resident data bytes (a file inode) or a list of the inode indices of its children (a directory inode); it walks the hardlink table, whose edges index two inodes each, and the xattr table, whose attributes carry an inline length-counted value. To report the total resident footprint it resolves the root inode 0 through its directory tree, summing the resident data bytes the file inodes it reaches contribute. For a well-formed file it prints a one-line JSON summary whose keys are format_version, volumes_defined, inodes_defined, file_inodes, dir_inodes, hardlinks_parsed, xattrs_parsed, and data_bytes, the total resident byte count reachable from inode 0 with a directory resolved as the sum over the inodes it lists. The same inode may be listed more than once, and by more than one directory, and each listing adds that inode's footprint again, so data_bytes is counted with multiplicity. Each key is defined in the format reference. The format is documented in...

Required artifacts include: `/app/environment`, `/app/environment/docs/disk-forensic-image-format.md`, `/app/environment/imgscan`, `/app/environment/src`, `/app/environment/testdata/valid`.

Author anonymous tagged this **hard** security task (gcc, c, security, memory-safety, hardening).

Time estimates: expert ~240 min, junior ~600 min.

Harbor timeouts: agent 1800s, verifier 1200s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `046007bc-953f-4f97-bc3d-3d642b0d55c9_submission_2026-07-17T16_16_44.223Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Dependency plan looks consistent locally but violates a hidden pin/conflict rule. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
