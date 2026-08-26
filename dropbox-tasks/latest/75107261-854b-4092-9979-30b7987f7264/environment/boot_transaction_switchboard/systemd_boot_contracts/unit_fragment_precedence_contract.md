# Unit Fragment Precedence Contract

Clause namespace: `FRAGMENT-*`

## FRAGMENT-1 Search tiers

Main fragments are sought in this precedence for the unit name:

1. administrator: `etc/systemd/system/`
2. transient: `run/systemd/system/`
3. vendor: `usr/lib/systemd/system/`

The highest-precedence ordinary unit file or `/dev/null` mask decides the main fragment. A mask at any tier suppresses the entire effective unit, including drop-ins from every tier. A lower-tier mask is not overridden by a higher-tier ordinary fragment.

Neutral example: if `run/systemd/system/demo.service` is a `/dev/null` symlink, an `etc/systemd/system/demo.service` ordinary file does not unmask it for loading; administrator unmask operations are required and apply only to the administrator tier.

## FRAGMENT-2 Aliases

A symlink whose target is another unit name in the same tier is an alias. Resolve aliases until a real fragment or mask is reached. Detect loops. An alias may not change unit type suffix or rewrite a template instance incorrectly. Only relative targets and `/dev/null` are valid.

## FRAGMENT-3 Templates and instances

For `name@instance.service`, prefer an exact instance fragment `name@instance.service`. Otherwise load `name@.service` and preserve the requested instance for specifier expansion. A non-instantiated template cannot enter a boot transaction unless install metadata supplies a valid `DefaultInstance`.

## FRAGMENT-4 Drop-in families

Drop-ins are gathered from directories named for:

- type family: `<type>.service.d/` style is not used; type-wide drop-ins use `<suffix>.d/` only when declared in this closed model as `service.d/`, `target.d/`, `mount.d/`, `automount.d/`, `path.d/`, `device.d/`
- dash-prefix families: for `a-b-c.service`, consider `a-.service.d/`, `a-b-.service.d/`
- template family: `name@.service.d/`
- exact unit: `name@instance.service.d/` or `name.service.d/`

Across tiers, for the same basename, the highest tier wins. Surviving basenames sort by raw ASCII. Apply families from broadest to most specific: type, then each dash-prefix from shortest to longest, then template, then exact.

## FRAGMENT-5 Sections and directives

Supported sections: `[Unit]`, `[Install]`, `[Service]`, `[Mount]`, `[Automount]`, `[Path]`, `[Target]`. Section ownership is enforced. Unknown directives on the compatibility roster remain visible in effective maps but do not influence modeled jobs.

List directives accumulate; an assignment of empty value resets that list. Scalar directives replace prior values and are not erased by an empty assignment unless the directive is listed as resettable-scalar in the merge rules consumed by the semantics capsule. Quoting and line continuation follow systemd-compatible backslash continuation and double-quote rules for this closed grammar.

## FRAGMENT-6 Effective ledger

Every loaded unit records chosen fragment path (logical), mask/alias/template origin, contributing drop-ins, reset events, normalized directive multimap, specifier expansions, and content digests in `effective.units`. Units referenced by the order but unused by the final transaction still require an accounted classification.

## FRAGMENT-7 Differences from upstream

Upstream systemd also searches `/etc/systemd/system/*.wants/` names differently for some alias cases and runs generators. This closed model uses only the three tiers above and does not execute generators.
