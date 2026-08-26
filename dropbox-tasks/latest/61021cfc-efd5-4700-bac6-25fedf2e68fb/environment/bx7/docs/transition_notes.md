# Capability modes and root rebinding

Two capability modes govern how the active root is rebound into the staged tree:

| Mode | Requirement |
|------|-------------|
| `cap_strict` | Packaging must complete a full pivot sequence before the staged tree is considered active. The generation seal for the row must be a positive odd integer. Bind-only rebinding alone is not sufficient under this mode. |
| `cap_relaxed` | Bind-only rebinding into the staged tree is acceptable. The generation seal for the row must be a positive even integer. |

The module under `/app/environment/bx7/` owns root rebinding and the generation seal consumed by linker cache and device materialization.
