# Formal rules index — CI runner cgroup attach

Normative identities and durable-state rules for fixture 49 rematerialization.
These documents are contracts and grammars, not a procedural patch guide.

## Section map

| Topic | Authoritative file |
| --- | --- |
| Artifact fields, authority split, REDUCE_HOME | `pact_r8.md` |
| Latch journal grammar and durable stamp authority | `pact_r8.md` (Durable latch journal) |
| Durable `.seg` grammar | `pact_r8.md` (Durable `.seg` grammar) |
| Combine-stage ownership (u9p) and Orch sequencing | `pact_r8.md` (Module ownership) |
| Parent-proc / durable-claim nest-cut notes | `bnd_q9.md` |
| Shallow-nest operator checks | `leaf_m2.md` |
| Build and run argv | `run_cmds.txt` |
| REDUCE_HOME formula comment | above `main` in `/app/environment/drv/cg_xmit.rs` |

## Authority boundaries (summary)

- Durable `.seg` state supplies the durable stamp and bits used for claim merge
  and for the persisted latch-journal `<stamp>` field.
- Runtime progress may be computed during rematerialization but does not replace
  the durable stamp when writing `c7.jrnl`.
- On-disk `c7.jrnl` is the sole latch authority for bag coherence and emit;
  reload it before emit.
- Orch sequences stages; `/app/environment/u9p` owns nest handshake arm-combine.
  Orch must delegate; equivalent inline arm-combine is outside the intended repair.
