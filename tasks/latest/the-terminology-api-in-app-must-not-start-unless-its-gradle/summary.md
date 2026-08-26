# The terminology API in `/app` must not start unless its Gradle dependency lock a

- **UUID:** `6cd2eab6-d607-4f4b-8c0a-66687b093ea9`
- **Slug:** `the-terminology-api-in-app-must-not-start-unless-its-gradle`
- **Category:** build-and-dependency-management
- **Difficulty:** hard

## Summary

The terminology API in `/app` must not start unless its Gradle dependency lock and Hugging Face asset lock agree on the exact local dataset revision used for synonym expansion. `/app/gradlew updateHfAssetLock check` must run offline, emit `/app/config/hf-assets.lock.json` from the local Hugging Face mirror, and enforce route and file policy from the release council transcript.

Lock regeneration currently yields malformed JSON; validation accepts stale revisions and forbidden public-route files; Gradle `check` proceeds while asset validation fails; Spring Boot starts with tampered locks; the public synonym route returns evaluation-only or preview-only aliases. The asset lock must record repository, revision, lock schema version, metadata and transcript digests, the Gradle dependency-lock digest, and each public route with permitted files, per-file checksum, and byte size.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
