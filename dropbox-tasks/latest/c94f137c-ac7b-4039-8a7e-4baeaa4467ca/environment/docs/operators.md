# Operator notes

Rebuild after changing Go sources:

```
cd environment && go build -o ../bin/claimdocketaudit ./cmd/claimdocketaudit
```

Run the practice audit:

```
claimdocketaudit audit \
  --docket-dir environment/fixtures/practice \
  --epoch 7 \
  --json-out out/claim_docket_audit.json
```

The auditor uses the Go standard library for SHA-256 and CRC32C (Castagnoli). Contract and settlement details live under environment/docs/.
