The orchard cold-hour ledger under `/app/environment` needs repair. Rebuild the Go CLI from source so replay mode regenerates deterministic `s7_ledger.jsonl`, `s7_audit.tsv`, and `replay_state.json` artifacts from manifest-relative inputs, while the original simple mode remains backward compatible.

The repaired pipeline must follow the contracts in `/app/environment/docs` for profile settings, environment overrides, sensor registry calibration, correction replay, Fahrenheit conversion, anchored bucket windows, interval credit, deterministic output, replay state, and atomic failure behavior.

Do not hand-write output artifacts or special-case the bundled fixtures. Implement the general Go pipeline so equivalent unseen manifests and feeds produce byte-stable results through the documented CLI.
