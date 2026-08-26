# An attacker controls the untrusted suffix of an OCI image and is trying to escap

Submission: `5df8652e-14e2-4067-9f02-680b00e711dc`  
Slug: `an-attacker-controls-the-untrusted-suffix-of-an-oci-image-an`  
Latest archive: `5df8652e-14e2-4067-9f02-680b00e711dc_submission_2026-07-16T11_43_15.638Z.zip`  
Revisions in Dropbox: 1

## Task summary

An attacker controls the untrusted suffix of an OCI image and is trying to escape the extraction root or replace protected operating system files. Decide whether the image is safe by implementing the extraction security gate defined in /app/spec. Create /app/layer_gate.c using only ISO C11 and the C standard library. Compile it with gcc -std=c11 -O2 -Wall -Wextra -Werror into /app/layer-gate. The binary accepts exactly POLICY MANIFEST OUTPUT and must analyze any valid revision 1 policy and LAYERS2 capture. Authenticate every listed layer then evaluate effective archive names after PAX and GNU overrides. Replay whiteouts hard links symbolic links and namespace changes exactly as specified. Surface path and link escapes pivot attempts protected-path mutations privilege escalation duplicate shadowing malformed markers namespace confusion and hard-link failures. A valid hostile image exits zero with a deny report. Malformed input exits two with no output. Keep stdout and stderr empty.

Required artifacts include: `/app/spec`, `/app/layer_gate.c`, `/app/layer-gate`, `/app/evidence/extraction.policy`, `/app/evidence/layers.manifest`, `/app/output/extraction-security.json`.

Author anonymous tagged this **hard** security task (containers, archive-extraction, path-traversal, privilege-escalation, supply-chain).

Time estimates: expert ~300 min, junior ~780 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `5df8652e-14e2-4067-9f02-680b00e711dc_submission_2026-07-16T11_43_15.638Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
