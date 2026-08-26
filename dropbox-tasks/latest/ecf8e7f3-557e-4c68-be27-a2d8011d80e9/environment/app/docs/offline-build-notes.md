Cargo builds are path-only and offline (`net.offline = true`).
pnpm overrides must use `/app/pnpm-store` file:// archives whose bytes match pin integrity.
`/app/.npmrc` must set `offline=true` and `store-dir=/app/pnpm-store`.
Release validates pins/lockfile/package.json offline — it does not need a live `pnpm install`.
