# Rutile platform layout

Strata directories at repo root describe ingestion schemas: `iam/`, `roles/`, `groups/`, `permissions/`, `cloud/`, and `rbac/`.
The product-facing `escalation-analyzer/` tree is a placeholder; the analyzer ships as escalctl plus internal export packages.

Analyzer export logic is distributed across several small Go packages at the environment root plus shared internal helpers. Each package contributes one stage of edge synthesis, gating, weighting, path tracing, or attestation folding invoked from the internal export runner. Operator rebuild and analyze commands are documented in `operator_cmds.md`.
