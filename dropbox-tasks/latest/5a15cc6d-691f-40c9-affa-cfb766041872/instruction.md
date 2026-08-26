Request admission security gate (`siggate`)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is a **perimeter authentication and anti-replay security control**. At
request admission, `/app/bin/siggate` must reject **forged** Harbor Request MAC
v1 (HRM-1) envelopes and **replayed** authentic envelopes before traffic is
admitted. Admit/deny outcomes are security decisions under the site profile.

The shipping binary still admits paths that violate that security contract.
Restore the gate so every outcome matches this instruction and the normative
security docs under `/app/docs/`. Leave `/app/bin/siggate` ready to run.

**Normative security docs (binding):**
`/app/docs/cli-surface.md`, `/app/docs/query.md`, `/app/docs/digest.md`,
`/app/docs/time.md`, `/app/docs/profile.md`.

Site security material: `/app/data/site.profile` and attestation vectors under
`/app/fixtures/gold/` (profile packing and profile-bound MAC binding for this
deployment).

```text
/app/bin/siggate verify --envelope <abs> --keyring <abs> --now <unix> --profile <abs> --seen <abs>
```

Success (exit 0, empty stderr): exactly one stdout line
`ok kid=<kid> digest=<content-digest>` (see docs).

Failure (exit 2, empty stdout): exactly one stderr line `error: <reason>`
(see docs for tokens and profile-ordered security checks).

After editing sources, rebuild `/app/bin/siggate` so happy-path stdout digests
stay byte-identical and multi-fault envelopes report the profile check-order
deny reason.
