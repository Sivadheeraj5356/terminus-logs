# Forest audit file and report contract

`forest-audit` certifies a bounded integer decision forest against a sequence of audit checks. The command has two forms:

`/app/bin/forest-audit`

`/app/bin/forest-audit MODEL AUDIT OUTPUT`

The explicit form requires exactly three absolute paths. The default form uses `/app/data/demo.forest`, `/app/data/demo.audit`, and `/app/output/certificates.json`. Success returns 0. Invalid model or audit data returns 2. Input or publication I/O failure returns 3. Invalid command use returns 64 with `forest-audit: E_USAGE`. Publication failure returns 3 with `forest-audit: E_PUBLISH`. Other diagnostics are written to stderr exactly as `forest-audit: TOKEN`. Relative explicit paths are invalid.

Both inputs are UTF-8 text. Blank lines and lines beginning with `#` are ignored, but physical line numbers still count them. Fields are separated by `|` and are never trimmed. Integers are canonical decimal text: `0` or an optional minus sign followed by a nonzero digit and more digits. Leading zeroes, `+`, and `-0` are invalid. Identifiers match `[A-Z][A-Z0-9_]{0,15}`.

## Model records

The first non-comment record is `MODEL|1`. Exactly one `BIAS|value` record is required. Remaining records may appear in any order.

`FEATURE|feature|min|max|step_cost`

`TREE|tree|weight|root_node`

`NODE|tree|node|feature|threshold|left_child|right_child`

A child is `N:node` or `L:-1` or `L:1`. A node follows its left child when the feature value is at most the threshold and its right child otherwise. A tree contributes `weight * leaf_value`; the forest score is the bias plus all tree contributions. Scores greater than zero predict `POS`; zero and negative scores predict `NEG`.

Feature ranges are inclusive, each width is at most 6, and step costs are 1 through 9. Tree weights are 1 through 20. Every tree root and node child reference must exist in the same tree. Tree graphs must contain no cycle, every declared node must be reachable from the root, and unreachable nodes are invalid, and every path must end at a leaf. Thresholds must lie between `min - 1` and `max` for their feature. The model may contain at most 8 features, 12 trees, and 80 nodes, and the product of all feature-domain sizes may not exceed 100000.

Model validation uses this priority, independent of record order: `E_MODEL_HEADER`, `E_MODEL_FIELDS`, `E_MODEL_IDENTIFIER`, `E_MODEL_NUMBER`, `E_MODEL_DUPLICATE`, `E_MODEL_RANGE`, `E_MODEL_REFERENCE`, `E_MODEL_TREE`, `E_MODEL_LIMIT`. The diagnostic includes the smallest physical line number belonging to the winning category as `forest-audit: TOKEN:line`. Missing or unreadable model input uses `forest-audit: E_IO`.

The canonical model text contains `BIAS`, then all `FEATURE` records sorted by feature identifier, all `TREE` records sorted by tree identifier, and all `NODE` records sorted by tree and node identifier, each followed by `\n`. The model hash is lowercase sixteen-digit FNV-1a-64 over those bytes, using basis `14695981039346656037` and prime `1099511628211`.

## Audit records

The first non-comment record is `AUDIT|1`. Records after it form one or more sessions.

`SESSION|session`

`POINT|feature=value,feature=value,...`

`PUSH`

`POP`

`SET|feature|value`

`LOCK|feature`

`UNLOCK|feature`

`BUDGET|value`

`CHECK|check`

`END`

A session begins with `SESSION`, followed immediately by one `POINT` containing every model feature exactly once. Point assignments may be in any order. The initial budget is 0 and no feature is locked. `SET`, `LOCK`, `UNLOCK`, and `BUDGET` update the current state. `PUSH` saves the complete point, lock set, and budget. `POP` restores the most recently saved state. `END` is valid only when the scope stack is empty. Session and check identifiers are globally unique. A check records the current state without modifying it.

Budget values are 0 through 500. Point and set values must be inside the declared feature range. Scope depth is at most 8. The audit may contain at most 12 sessions, 40 checks, and 200 non-comment records.

Audit validation uses this priority, independent of record order when categories can be compared: `E_AUDIT_HEADER`, `E_AUDIT_FIELDS`, `E_AUDIT_IDENTIFIER`, `E_AUDIT_NUMBER`, `E_AUDIT_DUPLICATE`, `E_AUDIT_REFERENCE`, `E_AUDIT_RANGE`, `E_AUDIT_STATE`, `E_AUDIT_LIMIT`. The diagnostic uses the smallest physical line number in the winning category as `forest-audit: TOKEN:line`. Missing or unreadable audit input uses `forest-audit: E_IO`.

## Counterfactual checks

For a check, consider every complete feature vector inside the model ranges. Locked features must remain equal to the current point. The cost is the sum over features of `step_cost * abs(candidate - current)`. Candidates with cost above the current budget are excluded. A counterfactual is a candidate whose prediction differs from the current prediction.

The selected counterfactual is the minimum by these rules in order: lower cost, fewer changed features, then the complete candidate value sequence in ascending feature-identifier order using normal integer comparison. If none exists, the check is certified. Tree votes in a counterfactual report are sorted by tree identifier.

## Report

The output is one compact JSON object followed by one newline. Keys appear in this order:

`schema`, `model_hash`, `checks`, `state_hash`.

`schema` is 1. `checks` remain in audit order. Each check object has keys:

`session`, `check`, `budget`, `point`, `locked`, `prediction`, `score`, `result`.

`point` is an array of `{feature,value}` rows sorted by feature identifier. `locked` is a sorted array of feature identifiers. `result` is either `{"kind":"certified"}` or an object with keys `kind`, `cost`, `changed`, `values`, `prediction`, `score`, `votes`. Its kind is `counterexample`; `values` has the same row shape and ordering as `point`; `votes` is an array of `{tree,leaf,vote}` rows sorted by tree identifier.

The state-hash text begins with `MODEL|model_hash\n`. For each check it appends:

`CHECK|session|check|budget|prediction|score|locked_csv|point_csv|kind\n`

For a counterexample it then appends:

`COUNTER|cost|changed|prediction|score|values_csv|votes_csv\n`

CSV feature values use `FEATURE=value` in feature order. Vote CSV uses `TREE=leaf:vote` in tree order. Empty CSV fields are empty strings. `state_hash` is lowercase sixteen-digit FNV-1a-64 over this text.

The command must fully read, parse, validate, evaluate, and serialize before changing the destination. It creates missing parent directories only for a successful publication. It writes a new regular file in the destination directory, sets mode 0644, and renames it over the destination without following a destination symbolic link, so the symbolic-link target remains unchanged. Any command, input, validation, evaluation, or publication failure preserves the prior destination bytes and removes temporary files and newly created empty parent directories.
