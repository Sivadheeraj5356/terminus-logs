Asterism Color offline release pack

The foundry masters under `/app/foundry-sources` are sealed. Do not rewrite them, the FEA sources, color UFOs, or `/app/asterism-ledger` inputs. Commission the offline release pack entrypoint named in `/app/asterism-spec/RELEASE_CONTRACT.md` so a default pack materializes `/app/out/colr-crate` from those masters using the pinned font toolchain already on PATH. Dropping finished fonts by hand is not enough: that pack command regenerates the crate, and checks re-run it before auditing the finished inventory. Do not fetch packages from the network.

Release coordinates, instance filenames, subset lists, archive naming, and retain flags live in `/app/asterism-ledger/release.toml` (companion subset lists and fvar named-instances sit beside it). Proof corpora live at `/app/proof-strings`. Exact CLI flags, absolute defaults, inventory rules, manifest schema, digest byte protocols, ZIP membership, axis bounds, palette labels, color glyph maps, layout retention, static name-table rules, shaping coverage, and reproducibility requirements are in `/app/asterism-spec/RELEASE_CONTRACT.md`.

A default pack run must fill exactly:

- `/app/out/colr-crate/AsterismColor-VF.ttf`
- `/app/out/colr-crate/AsterismColor-VF.woff2`
- `/app/out/colr-crate/static/AsterismColor-Text.ttf`
- `/app/out/colr-crate/static/AsterismColor-RoundedText.ttf`
- `/app/out/colr-crate/static/AsterismColor-CondensedSemibold.ttf`
- `/app/out/colr-crate/static/AsterismColor-WideBold.ttf`
- `/app/out/colr-crate/subsets/AsterismColor-LatinGreek.woff2`
- `/app/out/colr-crate/subsets/AsterismColor-UISymbols.woff2`
- `/app/out/colr-crate/release-manifest.json`
- `/app/out/colr-crate/AsterismColor-1.0.0.zip`

Relative CLI path arguments fail without writing a success pair. Editing the ledger alone must retarget instances, subsets, palettes, and archive naming without changing the pack entrypoint. When `retain_color` is false, color tables may be absent; when `retain_layout` is false, layout tables may be absent. When those flags stay true, color closure (including private-use color glyphs) and layout tables remain as specified in the contract.

Finished variable fonts must carry COLRv1 paint graphs, CPAL palettes Night and Dawn, private-use color glyphs, and Latin/Greek layout from the masters. Proof corpora must shape without `.notdef` for covered scalars. Static instance advances must match variable-font instancing at ledger coordinates, and static style names must follow the contract name-table rules. Manifest fields include `schema_version`, `family`, `version`, `source_date_epoch`, `profile_sha256`, `source_tree_sha256`, `artifacts`, `axes`, `named_instances`, `palettes`, and `tool_versions`, with digests and sizes matching on-disk artifacts per the contract. The archive holds only finished fonts plus the manifest, with stable epoch timestamps and lexicographic member order.

Identical inputs plus `SOURCE_DATE_EPOCH` must yield byte-identical crates across two absolute output roots. Rebuilds over an existing crate stay idempotent. Invalid ledgers abort without a success inventory.
