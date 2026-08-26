# The Sender Authorization Policy engine under /app/environment/engine is the

- **UUID:** `47439143-dd47-4f4d-b1c5-c99786d26ac4`
- **Slug:** `the-sender-authorization-policy-engine-under-app-environment`
- **Category:** security
- **Difficulty:** hard

## Summary

The Sender Authorization Policy engine under /app/environment/engine is the decision core of a mail anti-spoofing check: given a domain's published policy and a frozen DNS-like zone, it decides whether a connecting client IP is authorized to send mail for that domain. The semantics that policy is intended to have are written out in /app/environment/docs/sap-spec.md, and a few worked runs of the engine are in /app/environment/testdata/examples.

The engine as deployed does not fully honour those semantics: on some queries it answers differently from the specification, authorizing a sender the policy meant to refuse, or refusing one it meant to admit. How many such places there are, whereabouts in the engine they sit, and whether they are independent of one another is for you to establish; assume nothing about their number or their shape, and note that on a given query more than one of them may bear on the answer at once.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
