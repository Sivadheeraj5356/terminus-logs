# Legacy Record Decoder — Environment

## Structure

```
environment/
├── Cargo.toml              workspace root + library crate
├── src/                    library source
│   ├── lib.rs
│   ├── types.rs            shared record and state types
│   ├── model.rs            canonical-view helpers
│   ├── a1.rs               binary record reader
│   ├── b1.rs               compatibility trace builder
│   ├── c1.rs               malformed-input classifier
│   ├── compat.rs           compatibility shim
│   └── *_stub.rs           structural decoys (not on live path)
├── tools/
│   └── xscope/             checker CLI
│       ├── Cargo.toml
│       └── src/
│           ├── main.rs
│           ├── engine.rs   bundle validation logic
│           ├── report.rs   output writer
│           └── report_stub.rs
├── fixtures/
│   ├── raw/                binary fixture files
│   ├── text/               text export files
│   ├── bad/                malformed fixture files
│   └── interim/            false-green intermediate snapshot
├── docs/
│   ├── contract.md         output schema and round-trip rules
│   ├── layout.md           wire format and text export columns
│   └── notes.md            partial observability and error categories
└── scripts/
    ├── build_all.sh        build and install xscope
    ├── drive_suite.sh      per-group manual inspection helper
    └── clear_scratch.sh    remove build artifacts
```

## Build

```bash
/app/environment/scripts/build_all.sh
```

## Run checker

```bash
/app/environment/tools/bin/xscope \
    --all-samples \
    --bundle-out /app/output/legacy_record_bundle.json
```

See `docs/contract.md` for the bundle schema and `docs/layout.md` for the
wire format specification.
