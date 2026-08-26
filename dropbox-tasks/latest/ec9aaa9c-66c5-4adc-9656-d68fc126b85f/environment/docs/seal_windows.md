# Seal window selection

Graded digests do not always use the legacy `SEAL=` token.

Authoritative table: `SEAL_TABLE` in `/app/environment/fixtures/slices/q46.txt` (comma-separated tokens).
Authoritative modulus: `WINDOW_MOD` in the same slice file.

For each fixture set file under the matrix directory, let `set_stem` be the filename without the `.json` extension (for example `e3` for `e3.json`).

```
window_id = FNV-1a32(set_stem) mod WINDOW_MOD
```

`seal_window` on each certificate row is that `window_id` alone (not mixed with GEN).

Graded seal **token** selection mixes the current fold GEN into the table index:

```
seal_token = SEAL_TABLE[(window_id + GEN) mod len(SEAL_TABLE)]
```

where `GEN` is the 1-based generation for the line being folded (same value as `rev=`). Two folds that share a `window_id` but differ in GEN therefore may select different seal tokens and different digests even when `seal_window` matches.

Profile bands still control annex participation and `scope_letter`; they do not select the seal window.

Rematerialization drill: manifest_id `c1-alpha` appears under set stem `c1` and again under set stem `x4`, so later rows for that id must carry a different `seal_window` than the first pair.
