# Contain archive extraction attacks

An incident-response quarantine service received hostile nested submissions that escaped review roots, spoofed trusted paths, and exhausted workers. Harden the archive security boundary implemented under `/app/src` so it enforces the complete extraction security contract in `/app/docs/EXTRACTION_SECURITY.md`.

Keep the documented two-argument CLI. The hardened extractor must safely handle the documented TAR and ZIP inputs, recursively expand content-identified nested archives, preserve documented safe files and in-tree links, and enforce every path, entry-type, Unicode-collision, sparse-file, nesting, size, compression-ratio, and aggregate containment limit in the contract.

Safe-link compatibility includes `docs/report.txt`, symbolic link `docs/latest.txt` targeting `report.txt`, hard link `copies/report.txt`, executable file `docs/run-review.sh`, and ZIP executable file `records/run-verify.sh`, as detailed in the contract.

Duplicate archive entries are security failures even when they use the exact same spelling. In particular, two ZIP records with the same relative path such as `duplicate.txt` and `duplicate.txt` must be rejected before publication. ZIP local headers must reconcile with the central directory, unlisted local records must not be hidden ahead of reviewed entries, and a TAR must contain only zero padding after its two-block end marker. PAX sparse declarations and symlinked destination parents are also containment failures, even if an archive or filesystem abstraction presents them as ordinary entries or resolved directories.

Unsafe or malformed submissions must fail closed with a nonzero status. They must not modify anything outside the requested destination, publish a partial destination, or leave quarantine staging artifacts behind. The project must remain buildable and runnable without network access.
