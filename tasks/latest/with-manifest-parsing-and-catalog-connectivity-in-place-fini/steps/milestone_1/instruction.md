Helix monorepo manifests under `/app/priv/manifests` resolve local dependency pins from YAML/TOML, but the Mix pipeline in `/app` cannot yet read them or reach the MySQL approval catalog seeded in `helix_catalog`. Wire up the manifest parsing layer and a catalog client so `mix helix.parse` can produce a normalized build artifact.

Requirements:
- Implement `HelixPipeline.Manifest.Parser.parse_yaml/1` and `parse_toml/1` to load `/app/priv/manifests/services.yaml` and `toolchain.toml`. Both functions return maps with string keys.
- Implement `HelixPipeline.Catalog.Client.connect/0`, `ping/0`, and `query/3` using the MySQL settings in `/app/config/config.exs` (database `helix_catalog`, user `helix`).
- `ping/0` must run `SELECT 1` against the catalog and return `:ok` on success. On failure it must return `{:error, reason}` without raising or crashing the caller.
- `query/3` must return `{:ok, rows}` where each row is a map with string column names.
- Running `mix helix.parse` (after starting MySQL with `/app/scripts/start_mysql.sh`) must succeed and write `/app/build/parsed_manifest.json`.
- The JSON must include top-level keys `version`, `dependencies`, `toolchain`, and `platform`.
- `version` must be `"1"` from the YAML manifest.
- `dependencies` must list exactly `ecto_sql`, `myxql`, and `phoenix` with pins `3.11.3`, `0.7.1`, and `1.7.14`, sorted alphabetically by `name` (YAML source order is not preserved).
- `toolchain` must contain `elixir` `1.16.3` and `otp` `26.2.5`.
- `platform` must contain `os` `linux` and `arch` `amd64`.
- Do not modify files under `/app/priv/manifests`, `/app/priv/sql`, or `/app/priv/schemas`.
