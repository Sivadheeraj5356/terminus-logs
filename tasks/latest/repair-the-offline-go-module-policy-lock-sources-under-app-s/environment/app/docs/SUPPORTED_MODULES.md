# Supported modules

The offline mirror ships metadata for:

- `corp.example/root`
- `corp.example/lib`
- `corp.example/fork`
- `corp.example/fork-alpha`
- `corp.example/fork-beta`
- `corp.example/cgoish`
- `corp.example/platform`
- `corp.example/replace-root`
- `corp.example/wsroot`
- `corp.example/wslib`

Organization pins in `policy/pins.jsonl` cover platform-specific selections for `corp.example/cgoish` (`v1.0.0` on amd64, `v2.0.0-arm` on arm64).

## Mirror version selection

For each module path, read `/app/var/module-mirror/cache/download/<module>/@v/list` and take its first non-empty line as the candidate version tag. Then read `/app/var/module-mirror/cache/download/<module>/@v/<tag>.info` and use the `Version:` field when present. If the list file is missing, default to `v1.0.0.info`.

Non-conflicting smoke graphs must preserve these baseline selections after repair.
