# The `/app` project is `channelgate`, the subscription authorization check on a s

- **UUID:** `9594f9fa-bc95-4cb2-9f36-26883c019240`
- **Slug:** `the-app-project-is-channelgate-the-subscription-authorizatio`
- **Category:** security
- **Difficulty:** hard

## Summary

The `/app` project is `channelgate`, the subscription authorization check on a sensor telemetry bus. It reads a JSON batch on standard input, where each request pairs a channel rule a tenant has configured with the channel a subscriber is asking to read, and it writes one JSON result object on standard output.

Keep the input schema exactly `{"requests":[{"rule":"...","channel":"..."}]}` and the output schema exactly `{"admitted":[true,false]}`. Each result says whether the rule admits the entire requested channel; rules that cannot be parsed must report `false`.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
