"""Field index for beta-six lattice chronicle state artifacts (verifier cross-check).

Aligned with /app/docs/walk-seal-bind.md, /app/docs/hold-spine-ledger.md, and
/app/docs/lattice-chronicle-schema.md. Phase seal preimage order is normative in
walk-seal-bind.md. Residual scores are rounded to three decimal places before
snapshot_digest (see walk-seal-bind.md).
"""

# /app/state/dsc-peak-capture.json — schema thermal-cycle-capture-v1
# Top-level keys only. Window table lives in conching-window-table.json, not here.
CAPTURE_TOP_KEYS = ("schema", "batches", "capture_digest")
CAPTURE_DIGEST_BODY_KEYS = ("batches", "schema")
CAPTURE_BATCH_KEYS = ("batch_id", "formulation_id", "event_count", "hold_profiles")
CAPTURE_HOLD_PROFILE_KEYS = ("polymorph", "effective_hold_s", "temp_c")

# Legacy alias — do not list windows or other conching-window fields on capture JSON.
CAPTURE_KEYS = CAPTURE_TOP_KEYS

# /app/state/torque-residual-snapshot.json — schema lattice-residual-v1
# residual_score and effective_hold_s are nested, not top-level.
RESIDUAL_TOP_KEYS = ("schema", "residuals", "snapshot_digest")
RESIDUAL_DIGEST_BODY_KEYS = ("residuals", "schema")
RESIDUAL_ROW_KEYS = ("batch_id", "residual_score")

RESIDUAL_KEYS = RESIDUAL_TOP_KEYS

# /app/state/hold-spine-ledger.json — schema hold-spine-ledger-v1
HOLD_SPINE_TOP_KEYS = ("schema", "rows", "spine_digest")
HOLD_SPINE_ROW_KEYS = (
    "spine_seq",
    "batch_id",
    "polymorph",
    "effective_hold_s",
    "temp_c",
)

# /app/state/cross-batch-concordance.json
CONCORDANCE_TOP_KEYS = ("schema", "rows", "concordance_digest")
CONCORDANCE_ROW_KEYS = (
    "left_batch_id",
    "right_batch_id",
    "shared_polymorphs",
    "shared_effective_hold_s",
    "residual_gap",
    "concordance_score",
)

# /app/state/polymorph-walk-seal.json — schema phase-stabilization-seal-v1
# Ten-field phase_seal preimage includes concordance and closure bundle digests.
SEAL_TOP_KEYS = (
    "schema",
    "epoch",
    "capture_digest",
    "snapshot_digest",
    "spine_digest",
    "adjacency_digest",
    "concordance_digest",
    "audit_commitment",
    "ledger_triad_digest",
    "closure_bundle_digest",
    "phase_seal",
)

SEAL_KEYS = SEAL_TOP_KEYS

# /app/output/lattice-chronicle-report.json — schema beta-six-lattice-chronicle-v1
ATLAS_REPORT_KEYS = (
    "schema",
    "epoch",
    "phase_seal",
    "lattice_walks",
    "chronicle_digest",
    "walk_content_digest",
)

CHRONICLE_TOP_KEYS = ATLAS_REPORT_KEYS

# /app/state/chronicle-bind-manifest.json
MANIFEST_KEYS = (
    "schema",
    "kiln_traces_path",
    "conching_window_path",
    "shear_bonus_hz",
    "bind_digest",
)
