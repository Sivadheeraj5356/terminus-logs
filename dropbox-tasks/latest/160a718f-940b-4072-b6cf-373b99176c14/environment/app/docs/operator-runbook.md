# Operator runbook

Qualify a vault:

```bash
cd /app
make clean install
/app/bin/vault-qualify --vault /app/vault --output /output/recovery-set
```

Inspect committed heads:

```bash
/app/bin/vault-inspect --vault /app/vault
```

Validate a legacy archive:

```bash
/app/bin/vault-legacy-check --archive /app/vault/legacy/sample.json
```
