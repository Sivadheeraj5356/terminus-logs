# Link-plan input model

`arcplan INPUT_DIR OUTPUT_JSON` reads four UTF-8 files from `INPUT_DIR`. Identifiers use only ASCII letters, digits, `_`, `.`, or `-`. Unit references must name declared objects, archive references must name declared archives, and every malformed form described below is an exit-2 input error.

## aliases.tsv

The header is exactly:

`alias\ttarget`

The table may have no data rows. Each alias is unique, both fields are identifiers, and an alias cannot target itself. Targets may themselves be aliases, but the graph must be acyclic. Every symbol spelling in `symbols.tsv` and every `NEED` directive is replaced by its transitive terminal target before validation or linking. Output uses only terminal names. After canonicalization, a unit may still have at most one row for a given symbol, and two `NEED` directives may not name the same terminal symbol.

## objects.tsv

The header is exactly:

`unit\tarchive\torder\tcomdat`

At least one object row is required. `unit` is unique. `archive` is `-` for a loose object or an archive name for a member. Loose objects use order `0`; member orders are non-negative and unique inside their archive. `comdat` is `-` or a group name.

## symbols.tsv

The header is exactly:

`unit\tsymbol\tkind\tbinding\tsize`

Each canonical unit/symbol pair appears once. Row order has no semantic effect; only the `order` column in `objects.tsv` orders archive members. `kind` is `DEF`, `REF`, or `WEAK_REF`. `REF` and `WEAK_REF` use binding `-` and size `0`. A `REF` creates an unresolved need when no provider exists. A `WEAK_REF` never creates a need, never causes archive extraction, and never appears in `unresolved`. A `DEF` uses `STRONG`, `COMMON`, or `WEAK`; `COMMON` has a positive decimal size, while `STRONG` and `WEAK` use size `0`.

## command.txt

Blank lines are ignored, but at least one directive is required. Every other line is one directive:

- `OBJ unit` selects one loose object. Naming an archive member with `OBJ` is malformed and exits `2`.
- `ARC archive` scans one archive.
- `NEED symbol` adds the canonical symbol to the unresolved set at that point unless a provider already exists.
- `GROUP_BEGIN` ... `GROUP_END` forms a non-nested rescan group containing only `OBJ`, `ARC`, and `NEED` directives.
- `WHOLE_BEGIN` ... `WHOLE_END` forms a non-nested block containing only `ARC` directives.

A unit or archive may be named by at most one command directive, and a canonical `NEED` symbol may be named at most once. Groups and whole blocks cannot nest or overlap, and all blocks must close.

## Selection and resolution

Process directives from top to bottom. Selecting a loose object accepts it immediately unless its COMDAT group already has an owner. A normal archive is scanned once in ascending member order. Pull a not-yet-extracted member only when it defines at least one symbol currently unresolved. A whole block scans each archive once and pulls every not-yet-extracted member. For a group, make one ordered pass over every enclosed directive, including `NEED`, then repeatedly rescan only its `ARC` directives in listed order until a complete pass extracts no member. A `NEED` inside a group is therefore applied once, not on every rescan. Every archive member is extracted at most once.

Record a pulled member in `extracted_members` before COMDAT handling. The first accepted unit in a non-`-` COMDAT group owns it. A later pulled or selected unit in that group is omitted from `selected_units`, contributes no definitions or references of either strength, and is appended to `discarded_units` with reason `comdat:GROUP`.

For each accepted unit, consider all definitions before its references. Provider precedence is `STRONG` over `COMMON` over `WEAK`. A later higher-precedence definition replaces the current provider. Two strong definitions create one `duplicate_strong` error for the later provider and keep the first strong provider. Between common definitions, the larger size wins; an equal size keeps the earlier provider. Equal weak definitions keep the earlier provider. A strong reference is unresolved only when no accepted definition currently provides that canonical symbol; any later accepted definition removes it from the unresolved set.

At the end, `status` is `error` when `unresolved` or `errors` is non-empty, otherwise `ok`. Symbol rows are sorted bytewise by `name`; unresolved names are sorted bytewise; duplicate errors are sorted bytewise by `(symbol, first, second)`. Other arrays retain processing order.

## plan_sha256

The report's `plan_sha256` is `sha256:` followed by 64 lowercase hexadecimal digits. Hash the UTF-8 bytes of this exact transcript, excluding the digest field itself:

- `version<TAB>2<LF>`
- `status<TAB>STATUS<LF>`
- one `selected<TAB>UNIT<LF>` line per `selected_units` entry
- one `extracted<TAB>ARCHIVE<TAB>UNIT<LF>` line per `extracted_members` entry
- one `discarded<TAB>UNIT<TAB>REASON<LF>` line per `discarded_units` entry
- one `symbol<TAB>NAME<TAB>PROVIDER<TAB>BINDING<TAB>SIZE<LF>` line per `symbols` entry
- one `unresolved<TAB>NAME<LF>` line per `unresolved` entry
- one `error<TAB>KIND<TAB>SYMBOL<TAB>FIRST<TAB>SECOND<LF>` line per `errors` entry

Use the arrays in their final report order. Empty arrays contribute no lines.
