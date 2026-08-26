# Build the front-end for an "you're leaving our site" departure page at `/app` (s

- **UUID:** `19dab18f-8fd8-42a2-8070-c41889e662e6`
- **Slug:** `build-the-front-end-for-an-you-re-leaving-our-site-departure`
- **Category:** security
- **Difficulty:** hard

## Summary

Build the front-end for an "you're leaving our site" departure page at `/app` (served at `/` in the sandbox). It reads a destination URL and a partner name out of the page's own query string and shows a "Continue to X" link out to that destination; there's no backend, everything is static HTML/CSS/JS.

The catch: the destination and partner name both come straight from the URL, which means a visitor can be sent here with anything in those fields, including values crafted to look like one of the real partner links without actually being one, or to hijack the tab the link opens. `/app/LINKOUT_POLICY.md` is the binding spec - it names the actual allowed partner destinations, the exact element contract the verifier drives the page through, and the safety properties the departure link and the surrounding page have to satisfy.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
