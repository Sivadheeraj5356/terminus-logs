"""Build the EmbedServe operations bundle at image build time."""
from __future__ import annotations

import hashlib
import os
import textwrap

OUT = "/app/docs/embedserve-operations-bundle.md"

OPERATIVE = """# EmbedServe Inference Operations Bundle

**Document ID:** ES-OPS-2025-07-GATEWAY  
**Custodian:** ML Platform — EmbedServe Reliability Council

Practitioners must read this bundle in full. Section 11 (Amendment Register) supersedes earlier default tables in Section 4.

---

## Section 1 — Gateway scope

EmbedServe fronts local and remote model endpoints with a Rust tokenizer sidecar and PHP deployment inventory under `/app/data/embedserve_inventory.db`.

---

## Section 2 — Model card archive (reference)

Historical cards describe retired BERT and GPT-2 pilots. None change ratified policy; see Section 11.

---

## Section 3 — On-call digest (2025-05 through 2025-06)

Threads ES-881 through ES-940 mention Grafana panel refreshes and unrelated cache eviction noise. No operative policy changes appear in Section 3.

---

## Section 4 — Baseline inference defaults (initial ratification)

Initial values below were superseded by Amendment A-2025-07 in Section 11.

| setting_key | initial value |
|-------------|---------------|
| model_sandbox_enabled | false |
| allow_local_weight_files | true |
| mmap_model_weights | true |
| tokenizer_remote_code | true |
| tokenizer_trust_remote_code | true |
| tokenizer_max_vocab | 32000 |

---

## Section 5 — Tokenizer sidecar coupling (informational)

The tokenizer sidecar under `/app/environment/sidecar/tokenizer` links RSA for PKCS#1 v1.5 padding used in legacy artifact attestation. Lockfile advisories must gate component enablement.

---

## Section 6 — Static denylist era (retired)

Operations briefly maintained `/app/environment/config/static_cargo_denylist.json`. Inventory hardening now requires live advisory evidence from the bundled RustSec database.

---

## Section 7 — Deployment inventory tables

SQLite layouts are documented in `/app/environment/docs/inventory_schema.md`. Harden runs append `advisory_evidence` and `harden_runs` rows.

---

## Section 8 — Historical promotion threads (non-operative)

Retired investigations cite unrelated GPU driver rollouts. Do not extract defaults from Section 8.

---

## Section 9 — Capacity planning notes (non-operative)

Autoscaling worksheets and quota spreadsheets appear here for finance review only.

---

## Section 10 — Incident report schema (informational)

Prior JSON schemas for unrelated ranking services appear here. Harden report fields live in `/app/environment/docs/harden_contract.md`.

---

## Section 11 — Amendment Register (authoritative)

| Amendment | Date | Supersedes | Operative values |
|-----------|------|------------|------------------|
| A-2025-06 | 2025-06-18 | Section 4 | ratification_status **pending**; model_sandbox_enabled **false**; allow_local_weight_files **true**; mmap_model_weights **true**; tokenizer_remote_code **true**; tokenizer_trust_remote_code **true**; tokenizer_max_vocab **32000** |
| A-2025-07 | 2025-07-01 | Section 4 | ratification_status **ratified**; model_sandbox_enabled **true**; allow_local_weight_files **false**; mmap_model_weights **false**; tokenizer_remote_code **false**; tokenizer_trust_remote_code **false**; tokenizer_max_vocab **50257** |

When Section 4 disagrees with this table, **Section 11 controls**.

Offline advisory scanning uses:

```text
cargo audit --json --db /app/environment/fixtures/rustsec-advisory-db \\
  --manifest-path /app/environment/sidecar/tokenizer/Cargo.toml
```

Only tokenizer-role inventory components matching advisory package names are disabled.

---

"""

FILLER = """
## Appendix {idx} — Shift handoff notes {idx}

{text}

"""


def main() -> None:
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    parts = [OPERATIVE]
    paragraph = (
        "Shift lead reviewed tokenizer latency plots, attached queue depth exports, and noted "
        "artifact cache pressure was nominal. No amendment implied."
    )
    idx = 1
    while sum(len(p) for p in parts) < 220_000:
        block = textwrap.fill(paragraph * 5, width=100)
        parts.append(FILLER.format(idx=idx, text=block))
        idx += 1
    body = "\n".join(parts)
    doc_digest = hashlib.sha256(body.encode("utf-8")).hexdigest()[:16]
    with open(OUT, "w", encoding="utf-8") as fh:
        fh.write(body)
        fh.write(f"\n<!-- bundle_digest={doc_digest} -->\n")
    print(f"wrote {OUT} chars={len(body)}")


if __name__ == "__main__":
    main()
