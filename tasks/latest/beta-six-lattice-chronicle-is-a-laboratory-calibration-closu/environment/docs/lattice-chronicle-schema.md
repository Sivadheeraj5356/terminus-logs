# Polymorph evolution atlas schema

The chronicle artifact /app/output/lattice-chronicle-report.json uses schema beta-six-lattice-chronicle-v1.

Top-level chronicle keys are schema, epoch, phase_seal, lattice_walks, chronicle_digest, and walk_content_digest only. Peak-capture and residual digests belong in /app/state/ artifacts, not in the atlas JSON.

Each lattice_walks row binds one batch_id to its formulation_id, seed_polymorph from /app/lattice-invariant-catalog/formulation-catalog.json, dominant_polymorph computed from accumulated effective hold per polymorph window, residual_score from the lattice snapshot, quench_scale from that formulation, and transition when dominant_polymorph differs from seed_polymorph.

Dominant polymorph selection ranks polymorphs by total effective hold seconds, breaking ties by polymorph name ascending. A polymorph qualifies only when its accumulated effective hold meets hold_min_s for that window in the temper window table.

The atlas includes epoch and phase_seal copied from /app/state/polymorph-walk-seal.json. chronicle_digest is SHA-256 over stable JSON of an object with keys schema, epoch, phase_seal, and lattice_walks only (no digest fields inside the hashed body), using the same key-ordered sorted keys and Perl JSON::PP whole-number integer encoding defined in /app/docs/kiln-trace-contract.md. walk_content_digest is SHA-256 over stable JSON of the lattice_walks array alone. walk_content_digest must not include epoch or phase_seal. When epoch advances for unchanged lattice_walks, walk_content_digest stays stable while chronicle_digest changes.

Hidden verifier probes under ZONE-B6 may supply alternate temper windows or batch directories. Those fixtures are not bundled under /app/kiln-run-traces/.
