# Offline toolchain with incremental compilation

See `/app/docs/output-contract.md` for output schemas, divisor rules, replay expectations, and operator field definitions.

## Compile

```bash
node /app/environment/cli/driver.mjs compile --spec /app/environment/specs/operator.json --out /app/output
```

## Cache management

```bash
node /app/environment/cli/driver.mjs cache-reset
```

## Status preview

`node /app/environment/cli/driver.mjs status --trace /app/output/pass.trace.json` is diagnostic only. Parity checks may invoke `node --input-type=module`.
