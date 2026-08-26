# Build-cache SBOM and lockfile release guard

This lane is a **build-and-dependency-management** release guard: lockfile pins, SBOM-style digests, supply-chain closure, and offline reproducible rebuild — not application debugging.

## Dependency lock / SBOM workflow

1. **Lockfile tiers** — `rank_s0.yml` plus optional `*_resp.rsp` under `--reload` select the effective dependency scope (lock-tier precedence).
2. **Define-order lock traces** — KQDT blobs encode dependency pin order and tick budgets (supply-chain define pins).
3. **Compiler-wrapper SBOM segments** — KQWH wires contribute wrapper hash counts into the attestation.
4. **Release guard** — argv/wrapper authority blend, `ledger_bind` closure, and `cache_digest` must agree before publish.

## Artifacts

| Path | Role |
|------|------|
| `/app/output/kq_frames.ndjson` | Intermediate build-graph frames from the deck |
| `/app/output/kq_stage.ndjson` | Reproducibility staging ledger |
| `/app/output/kq_report.json` | SBOM-style attestation (`cache_digest` + `rows`) |

## Pin-mismatch and reproducibility

- Override env paths exercise **pin mismatch** release gates (argv/wrap/define).
- Identical decks must produce identical digests (**reproducible builds**).
- Denylist must not drop lockfile define pins or admit decoy argv entries.
