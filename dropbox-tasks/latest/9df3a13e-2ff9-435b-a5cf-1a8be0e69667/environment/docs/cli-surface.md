# CLI surface — waxlane-allot

Binary: /app/bin/waxlane-allot

## chalk

```text
waxlane-allot chalk --court /app/data/rink-lanes.json --lots /app/data/disk-packages.json --slate /app/state/chalk-slate.json --epoch /app/state/chalk-epoch
```

Writes the chalk slate only. Does not write the claim ledger. Does not invoke the allot solver.

## allot

```text
waxlane-allot allot --court /app/data/rink-lanes.json --slate /app/state/chalk-slate.json --ledger /app/output/wax-lane-claim-ledger.json
```

Reads court + chalk slate. Refuses if slate binding checks fail. Writes the claim ledger. Must not open the original wax-lots path.

## claim

```text
waxlane-allot claim --court /app/data/rink-lanes.json --lots /app/data/disk-packages.json --slate /app/state/chalk-slate.json --epoch /app/state/chalk-epoch --ledger /app/output/wax-lane-claim-ledger.json
```

Runs chalk then allot in one process.

## buff-catalog

```text
waxlane-allot buff-catalog --catalog /app/data/spray-catalog.json
```

Prints a decorative surface-buff listing. Not part of chalk or allot. Operators may ignore it for claim-board work.
