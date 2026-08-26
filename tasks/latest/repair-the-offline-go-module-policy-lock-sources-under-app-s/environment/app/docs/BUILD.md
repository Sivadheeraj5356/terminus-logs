# Build modpolicylock

From `/app`:

```bash
export PATH="/usr/local/go/bin:$PATH"
cd /app
go build -o /app/bin/modpolicylock ./cmd/modpolicylock
```

The verifier rebuilds the binary from sources before running checks. Prebuilt binaries under `/app/bin/` are not trusted unless they match a fresh build.

Environment variables:

- `MODPOLICY_OFFLINE=1` — required for offline resolution
- `GOPROXY=off` and `GOSUMDB=off` — set in the image
