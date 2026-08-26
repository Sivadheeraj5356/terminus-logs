# rpresolve

A command-line render-pipeline plugin resolver. Given a plugin **registry** and a
set of top-level **requirements**, it computes the **install set**: the single
version chosen for every plugin that must be installed, together with any
**conflict records** for dependencies that cannot be satisfied.

The program reads one JSON document from standard input — an array of resolution
cases — and writes one JSON document to standard output: an array of results, one
per case in the same order. An empty input array produces an empty output array.

## Input

Each case has a `registry` and a `requirements` map:

```json
{
  "registry": {
    "web": [
      {"version": "1.4.0", "deps": {"http": "^2.1.0"}},
      {"version": "1.3.0", "deps": {"http": "^2.0.0"}}
    ],
    "http": [
      {"version": "2.1.0"},
      {"version": "2.5.0"},
      {"version": "3.0.0", "yanked": true}
    ]
  },
  "requirements": {"web": "^1.0.0"}
}
```

* `registry` maps each plugin name to the list of its available versions. Each
  version entry has a `version` string, an optional boolean `yanked` (default
  `false`), and an optional `deps` map from a dependency plugin name to the
  constraint string that version declares on it.
* `requirements` maps a top-level plugin name to the constraint string required
  of it.

## Output

Each result is an object with two arrays:

```json
{
  "install": [
    {"name": "http", "version": "2.5.0"},
    {"name": "web", "version": "1.4.0"}
  ],
  "conflicts": []
}
```

* `install` lists every plugin that must be installed with its single chosen
  version, sorted ascending by plugin name.
* `conflicts` lists conflict records (see below), each `{"packages": [...],
  "dependency": d}` where `packages` is the set of requiring plugins whose
  declared constraints on `d` cannot be jointly satisfied — one entry when a lone
  requirer's own constraint is unsatisfiable, two when two requirers conflict —
  sorted ascending; the array itself is sorted by `dependency`, then by
  `packages`.

## Versions and precedence

A version string is `major.minor.patch` with an optional pre-release suffix
introduced by a hyphen, for example `1.2.0` or `1.2.0-rc.1`. Precedence follows
Semantic Versioning:

* Compare `major`, then `minor`, then `patch` numerically.
* A version **with** a pre-release suffix has **lower** precedence than the
  otherwise identical version without one (`1.2.0-rc1` < `1.2.0`).
* Two pre-release suffixes are compared identifier by identifier (identifiers are
  the dot-separated fields of the suffix). A purely numeric identifier is
  compared numerically; a numeric identifier has lower precedence than a
  non-numeric one; two non-numeric identifiers are compared by ASCII order. If
  every shared identifier is equal, the suffix with more identifiers has higher
  precedence (`1.0.0-alpha` < `1.0.0-alpha.1`).

## Constraint operators

A constraint string is a single operator expression. Missing trailing components
of an operand default to zero, and the operand may itself carry a pre-release
suffix.

* `=x.y.z` — matches exactly that version (including its pre-release suffix, if
  any).
* `>x.y.z`, `>=x.y.z`, `<x.y.z`, `<=x.y.z` — the ordinary comparison against the
  operand.
* `*` (also the empty string) — matches every version.
* `^` — a caret allows changes that do not modify the left-most non-zero
  component of the operand. Concretely, with the operand written `M.m.p` (missing
  components treated as absent, not zero):
  * `^M.m.p` with `M > 0` → `>=M.m.p <(M+1).0.0`.
  * `^0.m.p` with `m > 0` → `>=0.m.p <0.(m+1).0`.
  * `^0.0.p` → `>=0.0.p <0.0.(p+1)`.
  * `^M.m` (patch absent) → `>=M.m.0 <(M+1).0.0` when `M > 0`, else
    `>=0.m.0 <0.(m+1).0`.
  * `^M` (minor and patch absent) → `>=M.0.0 <(M+1).0.0` (this also covers
    `^0` → `>=0.0.0 <1.0.0`).
* `~` — a tilde bumps the last specified component's next-higher segment:
  * `~M` (only major given) → `>=M.0.0 <(M+1).0.0`.
  * `~M.m` or `~M.m.p` (minor given) → `>=M.m.0 <M.(m+1).0` (respectively
    `>=M.m.p <M.(m+1).0`).

The lower bound of a caret or tilde keeps the operand's pre-release suffix if it
has one (`^1.2.0-rc1` lowers to `>=1.2.0-rc1`).

## Selection

For a plugin, consider all active constraints on it (see transitivity). Among
its registry versions, keep the ones that are **admissible** (pre-release and
yanked rules below) and that satisfy **every** active constraint, and choose the
**highest** such version by precedence. Constraints are ANDed together: a version
must satisfy all of them at once.

## Pre-release admissibility

A pre-release version is excluded from selection **unless** it is explicitly
opted in. Specifically, a pre-release candidate whose core is `x.y.z` is
admissible for a given constraint only if that constraint names a pre-release
operand with the same core `x.y.z` (for example `>=1.2.0-rc1`, `<=1.2.0-rc4` or
`=1.2.0-rc1` all name the core `1.2.0`). Because constraints are ANDed, a
pre-release candidate is selectable only when **every** active constraint it must
satisfy names its core with a pre-release operand; a constraint such as `>=1.0.0`
that names no pre-release admits release versions only. A non-pre-release
(release) version is always admissible with respect to this rule.

A caret (`^`) or tilde (`~`) counts as a **single** constraint for this rule: it
names a pre-release operand exactly when its **written** operand carries a
pre-release suffix. So `^1.2.0-rc1` and `~1.2.0-rc1` each name the core `1.2.0`
and admit pre-releases of that core such as `1.2.0-rc2`; the expanded range is
evaluated as one unit, and the synthesized upper bound (for example the `<2.0.0`
that `^1.2.0-rc1` produces) is not a separate constraint that must independently
name the pre-release.

## Yanked admissibility

A version marked `yanked` is never selected **unless** an active constraint on
its plugin pins it exactly with `=x.y.z` naming that version; only then may the
yanked version be chosen (it is the sole version an exact pin can match).

## Transitivity

Resolution is transitive. When a version is chosen for a plugin, the constraints
that version declares in its `deps` become active on those dependency plugins,
which must then also be installed and resolved. A dependency's active constraints
are therefore the union of the top-level requirement on it (if any) and every
constraint declared on it by a currently chosen version of another plugin.
Choosing a higher version of one plugin may activate constraints that force a
lower version of another; the resolver revises earlier choices as needed so that,
whenever a fully consistent assignment of versions exists, it is found, always
preferring higher versions where the choice is free.

## Conflict records

When no assignment of versions can satisfy every plugin — that is, some
dependency `d` is left with an empty set of admissible satisfying versions no
matter how its requiring plugins are chosen — the resolver does **not** install
`d`. Instead it emits a conflict record `{"packages": [...], "dependency": d}`
naming the requiring plugins whose declared constraints on `d` cannot be jointly
satisfied. When a single plugin requires `d` and that plugin's own constraint
alone admits no version, `packages` holds just that one plugin. When two
requiring plugins conflict, `packages` holds exactly two, chosen as the
lexicographically smallest pair of requiring plugins whose two constraints alone
cannot be satisfied together. Only plugin sources are named: a top-level
requirement on `d` is never listed in `packages`, even when `d` also carries one.
All other plugins are still resolved normally, and a conflicted dependency's own
declared dependencies are not activated (it is not installed).

A conflicted dependency stays out of the install set even when it is itself one of
the top-level requirements. A top-level constraint on `d` never rescues `d` from a
conflict between its requiring plugins and never causes `d` to be installed anyway,
however satisfiable that top-level constraint may be on its own.

When conflicts are unavoidable, the resolver still chooses the assignment that
leaves only the conflicts that are genuinely forced: if a freely chosen version of
some plugin would introduce a conflict that a different admissible version of that
same plugin avoids, the avoidable conflict is not reported and the larger valid
install set is produced. Only the conflicts that remain under every such choice
are recorded.

This judgement covers everything a choice drags in transitively, not just the
plugin's own declared constraints: a version is avoidable if it, or anything its
selection pulls in further down the chain, would leave some dependency with no
satisfying version, while a lower admissible version of that same plugin keeps the
whole sub-resolution satisfiable. The preference for higher versions therefore
applies only among the versions that introduce no such avoidable conflict.

## sample_inputs.json

`sample_inputs.json` holds `{registry, requirements}` example inputs. Resolve them
with your build and compare against the contract above to check behaviour while
developing.
