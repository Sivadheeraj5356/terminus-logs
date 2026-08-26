# Orchard harvest crate mass-balance settlement

Orchard pickup settlement on the HARVEST1 lane is failing metrology QA. The pick-balance driver reads newline-delimited capture rows (pick, tare, supersede, spoilage) from an input feed and writes a per-zone balance report under /app/output. Independent replay audits report mismatches across generation ordering, tare offset windows and gram-band thresholds, void and refusal cadence, capacity accounting, zone label identity, settlement tie precedence, stamp lineage, and checkpoint resume parity.

The gram-conservation metrology model, checkpoint schema, digest preimages, and report fields are normative in /app/docs/harvest_rules.txt. Build and operator usage are in /app/docs/toolchain.txt.

Repair application sources under /app/environment, rebuild through the bundled Makefile, and produce reports by replaying feeds. Repeated runs on unchanged inputs should emit byte-identical report files. Warm checkpoint resume and invalid-checkpoint fallback are defined in harvest_rules.txt.
