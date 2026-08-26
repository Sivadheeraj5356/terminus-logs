# The terminology API in `/app` must not start unless its Gradle dependency lock a

Submission: `6cd2eab6-d607-4f4b-8c0a-66687b093ea9`  
Slug: `the-terminology-api-in-app-must-not-start-unless-its-gradle`  
Latest archive: `6cd2eab6-d607-4f4b-8c0a-66687b093ea9_submission_2026-07-17T21_25_34.257Z.zip`  
Revisions: 1

## Task summary

The terminology API in `/app` must not start unless its Gradle dependency lock and Hugging Face asset lock agree on the exact local dataset revision used for synonym expansion. `/app/gradlew updateHfAssetLock check` must run offline, emit `/app/config/hf-assets.lock.json` from the local Hugging Face mirror, and enforce route and file policy from the release council transcript. Lock regeneration currently yields malformed JSON; validation accepts stale revisions and forbidden public-route files; Gradle `check` proceeds while asset validation fails; Spring Boot starts with tampered locks; the public synonym route returns evaluation-only or preview-only aliases. The asset lock must record repository, revision, lock schema version, metadata and transcript digests, the Gradle dependency-lock digest, and each public route with permitted files, per-file checksum, and byte size. Operative policy lives only in `<!-- FINAL_RATIFIED:... -->` markers with inline `route`, `revision`, `files`, and `forbidden` attributes. Earlier `PROPOSAL` lines are non-operative. For a route, permitted and forbidden file sets accumulate across every FINAL_RATIFIED marker targeting that route; if markers disagree on `revision`, the last non-empty `revision` in transcript order is operative while accumulated file sets are retained. Digest and lifecycle rules are normative in `/app/docs/asset-lock-format.md`. Lock workflows honor `HF_MIRROR_ROOT` and `HF_TRANSCRIPT` from the process environment if present.

Required artifacts include: `/app/gradlew`, `/app/config/hf-assets.lock.json`, `/app/docs/asset-lock-format.md`.

Author anonymous tagged this **hard** build-and-dependency-management task (gradle, spring-boot, awk, huggingface-assets, dependency-locking, long-context).

Time estimates: expert ~270 min, junior ~780 min.

Harbor timeouts: agent 1800s, verifier 900s.

Oracle `solution/solve.sh` is present; tests write a Harbor reward via `tests/test.sh`.

Terminus-style flags (inspiration only): well-specified=yes, outcome-verified=yes, difficulty source=reasoning.

## Log summary

Archive `6cd2eab6-d607-4f4b-8c0a-66687b093ea9_submission_2026-07-17T21_25_34.257Z.zip` is a task submission, not a Harbor job. 1 revision zip(s) exist for this submission id. None of the sampled task files include `result.json` or `reward.txt`, so stump % cannot be computed from the archive. Run `stb harbor run` / Harbor locally if you need measured rates.

## Agent summary

No agent trajectories were packed in these submission zips. Likely failure modes from the instruction (not from a live run): Dependency plan looks consistent locally but violates a hidden pin/conflict rule.

## Stump the models?

- Local Harbor trials: none in the archive
- Valid-fail stump %: unknown
- Band: `no_logs`
