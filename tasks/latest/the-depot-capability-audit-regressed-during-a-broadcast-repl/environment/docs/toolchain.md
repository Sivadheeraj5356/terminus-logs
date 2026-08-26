# Toolchain

C depot service under `/app/environment` with OpenSSL HMAC and SHA-256 helpers.

## Build

```bash
bash /app/environment/ci/rebuild.sh
```

Produces `/app/environment/bin/depot`.

## Runtime

```bash
/app/environment/bin/depot audit --pack pack_alpha
```

Output path: `/app/output/admission_trace.json`.
