# DepotLock resolver contract

DepotLock converts an offline package index and a project manifest into one canonical lock report. All names and feature names are case-sensitive. Object-key and input-array order have no semantic effect, and unknown JSON fields are ignored. Inputs contain no duplicate logical entries, versions and constraints follow the grammar below, and feature atoms do not form feature-only cycles.

## Input documents

The index is an object with a `packages` object. Each key is a package name and maps to a nonempty array of version objects. A version object has required string `version`, optional boolean `yanked` (default `false`), optional object `features` (default `{}`), optional array `dependencies` (default `[]`), and optional array `conflicts` (default `[]`).

`features` maps a feature name to an array of atoms. An atom is another feature on the same version or `dep:<package>`. The expanded feature set is the smallest set containing every requested feature and every feature atom reachable from it. A `dep:<package>` atom activates every matching optional declaration of that package on the same version; when no such declaration exists it has no other effect.

A dependency object has required strings `name` and `constraint`. Optional fields are `features` (string array, default `[]`), `optional` (boolean, default `false`), `default_features` (boolean, default `true`), `targets` (string array, default `["*"]`), and `when_features` (string array, default `[]`). It target-matches when `targets` contains `*` or the project target. It guard-matches when every `when_features` name is expanded on its owner. A declaration is active when it target- and guard-matches and is either non-optional or activated by `dep:<name>`.

All active declarations are retained. Declarations with the same dependency name contribute every constraint and the union of requested features, while that name appears once in report dependencies. An active declaration requests `default` unless its `default_features` is `false`.

A conflict object has required strings `name` and `constraint` and optional `targets` with the same default and matching rule. It is active when its owner is selected, the named package is selected at a satisfying version, and its target matches. The declaration is effective regardless of which selected endpoint owns it.

The project has required string `target`, required array `roots`, and optional object `patches` (default `{}`). A root has required strings `name` and `constraint`, optional string array `features` (default `[]`), and optional boolean `default_features` (default `true`). Repeated roots retain every constraint and union their requested features. `patches` maps package names to exact version strings.

## Versions and availability

A version is three arbitrarily large nonnegative base-10 integers `major.minor.patch`; comparison is numeric by major, then minor, then patch. Leading zeroes do not affect comparison. Constraints are `*`, an exact version, a caret range, or a comma-separated intersection of `>=`, `>`, `<=`, and `<` comparisons. Whitespace around comma-separated terms and comparator operands is ignored.

`^1.2.3` denotes `>=1.2.3,<2.0.0`; `^0.2.3` denotes `>=0.2.3,<0.3.0`; and `^0.0.3` denotes `>=0.0.3,<0.0.4`.

Without a patch, a yanked version is unavailable. A patch replaces the available versions of that package with the named exact version, including when it is yanked, but the version must exist and satisfy every active constraint. A patch for a package that is not required has no effect.

## Resolution and canonical preference

For a selected version assignment, the active package set, requested features, and dependency declarations are their least fixed point starting from the roots. An assignment is valid exactly when every active package has one available selected version satisfying all its constraints, every requested feature exists on that version, no active conflict holds, and the active dependency graph is acyclic.

The package-priority list contains distinct root names in bytewise order, followed by every other index package name in bytewise order. A valid assignment's preference vector contains, for each priority name, its selected semantic version or an absent value lower than every valid version. Compare vectors lexicographically using numeric semantic-version comparison. The canonical assignment is the valid assignment with the greatest vector; this comparison is over complete assignments, not individual dependency declarations or input order.

## Conflict diagnostics

When no valid assignment exists, `problems` is the bytewise-sorted union of terminal reasons from all incompatible complete or terminal partial assignments. A reason at a terminal assignment is additive; other applicable reasons at that same assignment are still included.

- `missing-package:<name>` when a required name is absent from `packages`.
- `no-version:<name>` when a required package has no available version, or a selected version violates an active constraint or patch/yank rule. A missing package emits both this reason and `missing-package:<name>`.
- `missing-feature:<name>:<feature>` when a selected version lacks a requested feature.
- `incompatible:<a>@<version-a>:<b>@<version-b>` for an active conflict, with the two `name@version` endpoints in bytewise order.
- `cycle:<name>` for every package left after repeatedly removing the bytewise-earliest package whose selected dependencies have already been removed.

Rejected assignments contribute reasons only if every assignment is invalid. An unmatched `dep:<name>` atom contributes no reason.

## Report

The report has exactly the top-level keys `status`, `packages`, `build_order`, and `problems`. On success, `status` is `"ok"`, `problems` is `[]`, and `packages` contains one row per selected package in name order. Each row has exactly `name`, `version`, `direct`, `features`, and `dependencies`. `direct` is true for names present in roots. `features` is the sorted expanded requested-feature set, and `dependencies` is the sorted unique active-dependency name set.

`build_order` is dependency-first. Repeatedly append the bytewise-earliest unbuilt package whose selected dependencies are already present in the order. It contains every selected package exactly once.

On failure, `status` is `"conflict"`; `packages` and `build_order` are `[]`; and `problems` is the diagnostic union above. The CLI writes either report and exits 0. Malformed or unreadable input and an unwritable output need not produce a report and may exit nonzero.
