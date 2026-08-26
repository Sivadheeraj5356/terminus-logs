# Release graph

High-level architecture of one `release_pass.sh` run.

```
matrix (lane -> profile)
   |
   v
for each lane row:
   resolve profile  ->  profile_sha256
   idl_fingerprint.sh   (pack.order bytes + fragments + compat + provenance)  -> idl_digest
   tool_fingerprint.sh  (genabi sources)                                -> tool_digest
        |
        v
   cache decision (cache_stamp.sh + label_journal.sh)
        |  warm & current            |  cold / stale / torn
        v                            v
     reuse tree                  cmake configure  (configure_epoch++)
        |                            |
        +-------------+--------------+
                      v
        header present in build tree?
           no -> reconcile: regenerate header (generation_lineage++)
           yes -> continue
                      v
        cmake --build sdk_probe
           - genabi reads IDL + profile
           - writes generated/sdk.hpp + sdk.layout.json into the build tree
           - compiles src/probe.cpp against the generated header
                      v
        generated view  := sdk.layout.json
        compiled view   := ./sdk_probe
        status          := match if views agree else mismatch
                      v
        append record to probe.jsonl + lane record
        rewrite .sdk-lane.journal (both fingerprints, counters)

after all lanes:
   emit_artifacts.sh  ->  manifest.json, provenance.json, loader_journal.tsv
   trace.tsv accumulated per phase during the loop
```

Components:

- `tools/genabi/` — C++ generator: `parse` (IDL + profile), `layout` (offsets,
  alignment, padding), `render` (header + JSON layout), `digest` (IDL digest),
  `main` (CLI wiring).
- `src/probe.cpp` — includes the generated header and prints the compiled
  layout that the real compiler chose.
- `runbook/` — the shell orchestration described above.
- `build_defs/` + `CMakeLists.txt` — per-lane configure/build wiring.
