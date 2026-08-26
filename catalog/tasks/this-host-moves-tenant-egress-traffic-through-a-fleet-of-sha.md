# This host moves tenant egress traffic through a fleet of shaped network interfac

Submission: `1ed09eb2-8e0c-4323-bfe1-8712ef6228b7`  
Slug: `this-host-moves-tenant-egress-traffic-through-a-fleet-of-sha`  
Latest archive: `1ed09eb2-8e0c-4323-bfe1-8712ef6228b7_submission_2026-07-20T23_31_24.796Z.zip`  
Revisions: 3

## Task summary

This host moves tenant egress traffic through a fleet of shaped network interfaces, and every one of them needs its shaping policy provisioned from the link ledger registry. An active interface gets a unix group plus a nologin user with a fixed uid. It also gets a state directory under /var/lib/link-rate that the user owns, a systemd-networkd drop-in under /etc/systemd/network and a policy environment file under /etc/link-rate.d. Detached interfaces get no account and nothing on disk, though their ledger rows still belong in the chain. An interface carries months of daily egress volume rows, and its shaping numbers fall out of those rows once the ordered shaping adjustments and the smoothing pass have run over them. The whole run ends up summarized in a sealed manifest whose seal chains over every ledger row in registry order. The record layout, the arithmetic, the file contents, the manifest schema and the seal are all spelled out in /app/docs/LINKS.md, so read that before touching anything. The ledger records are packed in Redis on 127.0.0.1 port 6379. A small Slim API on 127.0.0.1 port 8080 serves the interface list, the per interface metadata and the shaping adjustments. Both come up with /app/scripts/start-services.sh. Shaping adjustments have to come from the running API, never from anything lying around on disk.

Required artifacts include: `/app/docs/LINKS.md`, `/app/scripts/start-services.sh`, `/app/bin/provision-link-rates`, `/app/out/link-manifest.json`, `/app/out/seal.hex`.

Author anonymous tagged this **medium** system-administration task (provisioning, systemd-networkd, traffic-shaping, user-management, redis, slim).

Time estimates: expert ~90 min, junior ~210 min.

Harbor timeouts: agent 1800.0s, verifier 600.0s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `1ed09eb2-8e0c-4323-bfe1-8712ef6228b7_submission_2026-07-20T23_31_24.796Z.zip` is a task submission, not a Harbor job. 3 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Identity, ACL, or permission mapping is close but fails the restore/authority contract. Archive restore produces files but misses hardlinks, logs, or idempotent repeat-restore rules. Service comes up but config, ports, or persistence do not match the verifier.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
