# Sealed reliability edges and evaluation resume

`plangen plan` keeps two durable surfaces under `/app/environment/var/` so
model-evaluation runs remain consistent across fold refits and interrupted
calibration jobs. A run that ignores them, or that reuses the wrong generation
of them, does not satisfy the evaluation contract.

## Fold digest

Every bundle has a fold digest. It is an unsigned 64-bit FNV-1a over a
canonical byte stream, written as sixteen lowercase hex digits with no prefix.

Canonical stream, in this order, each field terminated by a single ASCII
newline (`0x0a`):

1. `unit` as decimal digits
2. `cells` as decimal digits
3. `lanes` as decimal digits
4. `bins` as decimal digits
5. for every fit-fold row in bundle order: `raw`, comma, `hit`, comma, `lane`
6. a single line containing exactly three ASCII hyphens: `---`
7. for every rim row in bundle order: `raw`, comma, `hit`, comma, `lane`

FNV-1a parameters: offset basis `14695981039346656037`, prime `1099511628211`,
64-bit wrapping (the same parameters as Go's `hash/fnv` 64-bit FNV-1a). An empty
rim still contributes the `---` separator line after the fit rows.

Two bundles that differ in any of those fields have different digests.

## Fit store

Root: `/app/environment/var/fitstore/`

The image creates `/app/environment/var/fitstore` and `/app/environment/var/run`
at build time. `Seal` may mkdir digest and family directories under the fitstore
root when writing artifacts. Callers that plant or inspect store entries may
mkdir the same trees.

For fold digest `D` and family name `F` (`hist`, `iso`, or `giso`), the store
holds:

```
/app/environment/var/fitstore/<D>/<F>/edges.json
/app/environment/var/fitstore/<D>/<F>/meta.json
```

`edges.json` is a JSON array of exactly `bins - 1` integers: the equal-mass
edges for that family on that fold, per `/app/environment/docs/contract.rst`
section 3 (fit fold maps applied to fit rows and rim rows together).

`meta.json` is a JSON object:

```json
{"digest": "<D>", "family": "<F>", "bins": <bins>}
```

`Seal` writes both files for the current fold after fitting. `Recall` returns
edges only when `meta.json` exists, its `digest` equals the current fold
digest, its `family` matches, and its `bins` equals the bundle's `bins`.
Entries under any other digest directory must be ignored for the current fold.
Looking up by family name alone across digests is not this rule.

Measurement, selection, and emission of `deviation` must use recalled edges for
the current digest. Recomputing equal-mass edges from the fit fold alone is not
sufficient when the rim is non-empty. When no valid recall exists for a family,
edges are computed under `/app/environment/docs/contract.rst` section 3 (fit and
rim together) and sealed before use. Edges drawn from a rung's own rows are
never valid store contents.

Foreign-digest directories may be left on disk by earlier runs. A correct plan
must not read them for the current fold.

## Plan journal and lock

Root: `/app/environment/var/run/`

For destination path `--out`, let `base` be the final path component (the file
name). Then:

```
/app/environment/var/run/<base>.lock
/app/environment/var/run/<base>.journal
```

The lock file's contents are the current fold digest as sixteen hex digits and
one trailing newline. The journal is a JSON object:

```json
{"digest": "<D>", "floor": <strength>, "marks": [<severity>, ...]}
```

`floor` is the highest strength already committed in `marks` for this digest,
or `0` when `marks` is empty. A later `plan` over the same destination and the
same fold digest must treat `floor` as a lower bound on the first rung's
chosen strength (and therefore on every later rung, since strengths never
decrease). A journal whose `digest` does not match the current fold is stale:
it is removed together with the lock before planning proceeds, and the floor
is `0`.

During a successful plan, each accepted rung appends its severity to `marks`
and raises `floor` to that rung's strength. When the plan finishes with an
accepted assignment, both the lock and the journal are removed. When the
ladder is infeasible, the destination is removed (see
`/app/environment/docs/plan-format.rst`), and the lock and journal for that
destination are removed as well. A completed run never leaves a lock or journal
behind.

An interrupted earlier run may leave a lock and a partial journal. The next
`plan` for that destination must honor a matching digest's floor, or clear a
mismatched digest, as above.

## Interaction with the calibration contract

`/app/environment/docs/contract.rst` defines every number. This page defines
which durable artifacts those numbers may be read from or written to. A document
that matches that arithmetic on fit-only edges, or that was produced by reusing
foreign-digest edges, or by ignoring a matching journal floor, does not satisfy
the tool.
