# We have an application-security incident in `/app/sanitizer.py`: the gateway's i

Submission: `e291e403-f7f7-493d-9804-6284c93e57de`  
Slug: `we-have-an-application-security-incident-in-app-sanitizer-py`  
Latest archive: `e291e403-f7f7-493d-9804-6284c93e57de_submission_2026-07-18T05_41_39.646Z.zip`  
Revisions in Dropbox: 2

## Task summary

We have an application-security incident in `/app/sanitizer.py`: the gateway's input firewall is vulnerable to parser differential attacks, active URL-scheme smuggling, prototype-pollution key injection, and Unicode spoofing at a trust boundary. Patch the vulnerable security control and add the missing SQLite decision ledger used by incident responders. The default files remain `/app/input.jsonl`, `/app/policy.json`, `/app/output.jsonl`, `/app/rejected.jsonl`, and `/app/security_audit.sqlite`. Keep the existing CLI overrides and add `--audit-db` for the ledger path. Each submitted gateway event is accepted only when it contains exactly a non-empty string `id` and a `payload` of any JSON type. Accepted event IDs are stored only after the same NFKC normalization and control/bidirectional-character removal used for payload strings; use that normalized ID consistently in output records, hash-chain material, and the SQLite ledger, and reject the envelope if the normalized ID becomes empty. Treat the implementation like a small OWASP-style input validation and output integrity repair. An accepted event must be unambiguous RFC 8259 JSON: `NaN`, `Infinity`, `-Infinity`, and a blank physical line are `invalid_json`, never silently accepted or skipped. Object keys are security-sensitive data, not display text. Before duplicate, envelope, blocked-key, operator-key, and URL-key decisions, canonicalize every key with Unicode NFKC and remove U+0000-U+001F, U+007F-U+009F, and bidirectional formatting controls. Key aliases that then become equal under case-insensitive comparison count...

Required artifacts include: `/app/sanitizer.py`, `/app/input.jsonl`, `/app/policy.json`, `/app/output.jsonl`, `/app/rejected.jsonl`, `/app/security_audit.sqlite`.

Author anonymous tagged this **hard** security task (debugging, sqlite-audit-ledger, security-gateway, owasp-input-validation, cwe-20, cwe-1321, parser-differential, prototype-pollution, url-scheme-smuggling, unicode-security, tamper-evident-audit).

Time estimates: expert ~180 min, junior ~480 min.

Harbor timeouts: agent 1800.0s, verifier 450.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=mixed.

## Log summary

Dropbox archive `e291e403-f7f7-493d-9804-6284c93e57de_submission_2026-07-18T05_41_39.646Z.zip` is a task submission, not a Harbor job. 2 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from Dropbox contents. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Security boundary is incomplete: a forbidden identity, path, or privilege still leaks through.

## Stump the models?

- Local Harbor trials: none in Dropbox zip
- Valid-fail stump %: unknown
- Band: `no_logs`
