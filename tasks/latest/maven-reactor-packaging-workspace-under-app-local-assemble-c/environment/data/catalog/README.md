# Catalog

Scenario packs under `data/scenarios/` feed the packaging lattice simulator.
Each pack carries toolchain and path-slot fields consumed by the transforms.
The lattice processes every `*.json` pack in that directory.

## Tokens
- path_lane: real, leak, none, stub
- stub_gate: refuse, allow

## Selection contract
- classifier_pick uses the real id for toolchain_arch. Missing real id falls back to the stub id.
- classpath path_lane is real with a classifier jar present. Stub jar alone yields stub. Empty yields none. bind_ok matches real only.
- module-path path_lane is real with a classifier jar on that mode. Classifier absent on module-path with classpath still holding a classifier or stub jar yields leak and a failed bind. Empty yields none.
- stamp_bind and soname_mark use the real stamp and soname for the selected toolchain arch.
- stub_gate is refuse with a real toolchain classifier present. Otherwise allow.

## Local assemble rule
- Case `assemble_ok` is true when packaging stages finish and write a successful local assemble marker for that pack.
- Case `assemble_ok` is independent of per-mode `bind_ok`. A pack may keep `assemble_ok` true while one path_mode reports `bind_ok` false.
- Claim file `/app/output/reactor_claim.json` sets `assemble_ok` true only when every case has `assemble_ok` true, and sets `checked` to the number of cases. The claim is local assemble status only.

## Ledger JSON schema
Top level:
- `cases` (object): map from case_id string to case object

Case object:
- `case_id` (string)
- `entries` (array): exactly two row objects, one per path_mode
- `assemble_ok` (boolean): local assemble rule above
- `state_hash` (string): 64 lowercase hex chars

Row object:
- `case_id` (string)
- `path_mode` (string): `classpath` or `module-path`
- `classifier_pick` (string)
- `path_lane` (string): one of the path_lane tokens
- `stamp_bind` (string)
- `soname_mark` (string)
- `stub_gate` (string): one of the stub_gate tokens
- `bind_ok` (boolean)
- `row_token` (string): 64 lowercase hex chars

Claim object:
- `assemble_ok` (boolean)
- `checked` (number): integer count of cases

## Exact digest formulas
All digests are SHA-256 over UTF-8 bytes, emitted as 64 lowercase hex characters.

`row_token` input string (pipe-separated, no spaces):
```
{case_id}|{path_mode}|{classifier_pick}|{path_lane}|{stamp_bind}|{soname_mark}|{stub_gate}|{bind_ok}
```
where `{bind_ok}` is the literal `true` or `false`.

`state_hash` input string (sorted map print of the two path_mode tokens):
```
{classpath={classpath_row_token}, module-path={module_path_row_token}}
```
Exact punctuation: opening `{`, key, `=`, token, `,` then a single space, next key, `=`, token, closing `}`.
