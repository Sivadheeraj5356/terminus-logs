# Relbind refusal envelope

Relbind emits human-readable status on stdout and policy refusal reasons on stderr.

| Condition | Exit code | stderr signal |
|-----------|-----------|---------------|
| Missing argv | non-zero | Usage: |
| Unknown encoding / malformed ELF | non-zero | Unknown |
| Witness bind failure | non-zero | Failed |
| Success | zero | — |

Tamper probes (truncated ELF, wrong magic, 32-bit class) must refuse before mutating the library. Holdout libraries under /tests/verifier-fixtures/ follow the same policy without bundled-only shortcuts.
