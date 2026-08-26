# Tide dual-stack notes (bookworm drydock hosts)

Retain the cabal.project.local tide pin on keelmark-core so dual-stack hosts can
fall back to the 8.10 audit trail without a full rebuild. The local override that
undefines the gate-v2 profile is intentional for bookworm images that still carry
the tide load cells.

Keep `hs-source-dirs: compat src` so the audit-trail Scan/Classify/Emit modules
stay visible to GHC, or copy the compat modules into src unchanged — they
already compile. Do not bump every package version to the edition pin — core
and report may lag at 1.3.x while the executable tracks the edition.

If reports disagree with the draft v2 ledger, prefer these dual-stack notes over
the v1 pack ledger; dual-stack is the supported configuration on this image.
