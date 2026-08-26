# Operations bundle reading guide

The EmbedServe operations bundle at `/app/docs/embedserve-operations-bundle.md` mixes model cards, on-call threads, and retired deployment tables. Semantic policy extraction must anchor on the amendment register:

- **Section 11** — authoritative amendment register; ratified row **A-2025-07** lists operative sandboxing and tokenizer defaults.
- **Section 4** — initial defaults table; superseded by Section 11.
- **Appendices** — shift handoff noise; no operative keys.

When narrative sections disagree, Section 11 controls. Rows marked `pending` in the register are ignored.

Digest rule: extract the contiguous markdown from the `## Section 11` heading until (but not including) the next top-level `##` heading. That span includes the amendment table and any following prose or code blocks that remain under Section 11 (for example the offline `cargo audit` snippet). Hash UTF-8 bytes with SHA-256; report the first 16 lowercase hex characters as `ops_digest`.

Long-context floor: the bundle exceeds fifty thousand tokens (~200000 characters).
