# Model registry integrity

Model dependencies (`huggingface` ecosystem) are pinned not just to a
version but to **artifacts**: explicit files in the registry snapshot,
each with a SHA-256 digest recorded in the ledger row. This chapter
defines the integrity obligations on those pins. The rule here is stated
as in force; the quantifier was tightened by amendment after the Third
Edition (chapter 16), and Third-Edition-era phrasing survives in case
study two.

## Why artifact pins exist

A package ecosystem gives the gate a natural unit of integrity — the
archive the registry serves for a version. Model registries do not: a
"model" is a directory of loosely coupled files (configs, tokenizers,
vocabularies, weights, adapters), any subset of which a service might
load, and registry revisions can rewrite individual files. The ledger
therefore pins the exact files a build is entitled to read, by path and
digest. The pinned set is a statement: *these bytes, and no others, are
this dependency.*

The integrity report is produced outside the policy (the audit tooling
hashes the snapshot with OpenSSL and emits a path-to-digest map — see the
registry snapshot document for the procedure). The gate's job is to
compare that report against the pins.

## The verification rule

A model dependency verifies when **every** pinned artifact is present in
the integrity report **and** matches its pinned digest exactly. The
quantifier is universal and the findings are per-condition:

- A pinned path **absent** from the integrity report yields the reason
  `artifact-missing`. An absent path means the snapshot does not contain
  the file the ledger promises — a broken snapshot sync, a withdrawn
  upstream file, or a pin typo — and the build cannot be allowed to
  resolve the model some other way.
- A pinned path **present but with a different digest** yields the reason
  `digest-mismatch`. The file exists and is not the file that was pinned:
  an upstream in-place rewrite, a corrupted sync, or tampering. There is
  no "close enough" tier and no allowance for metadata-only differences —
  the digest is over the bytes.

Both reasons are rejections, and both can apply to the same dependency at
once (one pinned file missing, another rewritten). A dependency with five
pinned artifacts, four of which match perfectly, is rejected — four
verified files do not vouch for a fifth. The board tightened this language
deliberately: the earlier, weaker phrasing ("a dependency verifies when a
pinned artifact matches the report") dated from when models were pinned as
single archives, and it became a loophole the moment multi-file pins
arrived. The current rule's quantifier is *every*, and implementations
must fail closed on the full pinned set.

Model dependencies with an empty artifact list do not occur in practice —
the ledger tooling refuses to admit a `huggingface` row without pins — and
the gate is not required to define behavior for them.

## Relationship to quarantine

Integrity verifies *identity*: the snapshot bytes are the pinned bytes.
Quarantine (chapter 09) records *judgment*: these identified bytes must
not be used. The two compose without shortcuts in either direction — a
quarantined artifact whose digests all match is rejected for the
quarantine, and a mismatched artifact that matches no quarantine entry is
rejected for the mismatch. In the unhappy case of both, both reasons are
recorded. Note that quarantine matching runs against the **pinned**
digests (the ledger's statement of identity), while integrity matching
compares pins against the **computed** report; the distinction matters
precisely when the two disagree.

## Operational notes

The registry snapshot is content-addressed and append-only in normal
operation, so `digest-mismatch` in a healthy pipeline is rare and is
treated as an incident signal, not noise: the on-call runbook has the
gate's rejection paging the model-platform rotation, because the
alternatives (silent rewrite upstream, corruption in the mirror) are both
serious. `artifact-missing` is more often mundane — an incomplete snapshot
sync — but gets the same fail-closed treatment because the gate cannot
tell the mundane cause from the serious one.

Teams occasionally ask for a "grace" mode during model rollouts, where a
new revision's artifacts are pinned before the snapshot sync completes.
The board has declined every time: the correct sequence is sync first,
then advance the ledger generation with the new pins. The gate has no
notion of a pending pin.
