# Hugging Face asset lock format

The asset lock at `/app/config/hf-assets.lock.json` pins dataset files used by API routes.
Required fields: `lock_schema_version`, `repository`, `revision`, `source_metadata_digest`,
`transcript_digest`, `gradle_lock_digest`, and `routes` (each with `route_id` and `files`
containing `path`, `sha256`, and `bytes`).

Regenerate with `./gradlew updateHfAssetLock`. Validate with `./gradlew validateHfAssetLock`.

## Update and validation lifecycle

`updateHfAssetLock` publishes the lock atomically. If generation fails, the previously valid
lock remains byte-for-byte unchanged and no partial lock is left behind.

`validateHfAssetLock` validates the current lock file without invoking `updateHfAssetLock` and
without modifying the lock or its source inputs. Validation must not rewrite
`/app/config/hf-assets.lock.json`, modify the local mirror, transcript, route config, or Gradle
lockfiles. Malformed or stale locks must remain unchanged after validation fails.

`check`, `bootRun`, and application startup may depend on validation, but validation must never
depend on lock generation. `check` and startup must reject invalid locks rather than repairing
them; only an explicit `updateHfAssetLock` may regenerate the lock.

## Transcript policy

Policy for permitted and forbidden files is defined in the release council transcript using
FINAL_RATIFIED markers with inline `route`, `revision`, `files`, and `forbidden` attributes.
For a route, `files` and `forbidden` accumulate across every FINAL_RATIFIED marker targeting
that route. When markers disagree on `revision`, the last non-empty `revision` in transcript
order overrides earlier ones; accumulated file sets are retained. Unrelated routes do not affect
the selected route. `PROPOSAL` lines never define operative policy.

Lock workflows honor `HF_MIRROR_ROOT` (default `/data/hf-mirror`) and `HF_TRANSCRIPT`
(default `/app/docs/release-council-transcript.md`) when set in the environment.

## Digest rules

- `transcript_digest` — SHA-256 of raw transcript bytes.
- `source_metadata_digest` — SHA-256 of compact sorted-key JSON for the operative revision's
  `metadata.json` (formatting differences such as key order, indentation, or harmless whitespace
  must not change the digest; semantic value changes must).
- `gradle_lock_digest` — SHA-256 of concatenated records for every `*.lockfile` directly under
  `/app/gradle/dependency-locks/`, sorted by filename using bytewise lexicographic order. Each
  record is the filename as UTF-8, one NUL byte (`0x00`), then the lockfile body with CRLF
  normalized to LF.
- Route file `sha256` — SHA-256 of raw mirror file bytes; `bytes` is the octet length.
