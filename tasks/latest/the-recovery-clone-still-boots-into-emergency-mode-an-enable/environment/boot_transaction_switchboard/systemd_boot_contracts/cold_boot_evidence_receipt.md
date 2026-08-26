# Cold Boot Evidence and Receipt

Clause namespace: `EVIDENCE-*`

## EVIDENCE-1 State directory

On acceptance, `var/lib/unitgraph/` contains exactly:

```
generation
accepted.order
effective.units
enablement.state
transaction.jobs
boot.trace
change.account
reconcile.receipt
```

No other members are permitted.

## EVIDENCE-2 Record meanings

- `generation`: canonical next integer, decimal, LF-terminated
- `accepted.order`: binds `order_id`, `order.seal` digest, pre/post generations
- `effective.units`: every loaded unit's fragment origin, drop-ins, directives, expansions, classifications
- `enablement.state`: class plus exact link evidence lines
- `transaction.jobs`: jobs and originating edges
- `boot.trace`: deterministic event roster with logical step, unit, job transition, cause edge or predicate, public outcome, supporting fragment/device digest; no timestamps
- `change.account`: authorized mutations
- `reconcile.receipt`: commits immutable yard identity, vendor seal, order seal, complete poststate administrative tree, and the seven other state records with logical closure

## EVIDENCE-3 Cold replay

After staging mutations in a private shadow, launch a new process that receives only the staged yard root and sealed order paths. It must reread all unit tiers, symlinks, facts, devices, and order members from bytes. It cannot consume the builder's graph, cache, decisions, mutation list, or open input descriptors. Reconstruct effective units and the entire transaction; compare with staged records. Mismatch rejects and restores.

## EVIDENCE-4 Receipt stability

Reopen the published yard in a second process and recalculate the receipt before returning success. Receipts exclude absolute paths, traversal order artifacts, inode, owner, process data, locale, current time, temporary labels, and map iteration order. Repeated accepted orders and relocated equivalent yards retain byte equality of administrative trees, state records, link targets, and receipt.

## EVIDENCE-5 Mutation custody

Snapshot administrator tier and `var/lib/unitgraph/` before any write. Reject hard-link substitution, rename escape, intermediate symlink traversal, partial generation advance, and cross-device publication. Remove all private shadows after success or failure. Injected write or replay faults must restore exact prestate.

## EVIDENCE-6 Idempotence

An order already committed at the current generation is a verified no-op that reproduces its receipt without rewriting mutable bytes.

## EVIDENCE-7 Neutral example

A trivial yard with `app.service` static and `multi-user.target` wanting it yields `boot.trace` steps that start `app.service` then complete `multi-user.target`, with `reconcile.receipt` covering `effective.units` and `transaction.jobs` digests.

## EVIDENCE-8 Omissions

This contract omits journald export, persistent catalog databases, and live `systemctl show` bus properties.
