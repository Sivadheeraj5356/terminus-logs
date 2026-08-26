Spreadsheet formula engine contract

The input JSON contains sheets, optional names, and optional edits. Each sheet has a name and a cells object. A fully qualified cell id is Sheet!A1. Formula values are strings whose first character is =. Edits are applied in input order after the initial workbook is loaded.

Outputs are parse.json, formulas.json, deps.json, order.json, values.json, errors.json, recalculation.json, lineage.json, audit.json, metrics.json, and summary.json. Every file is one JSON object followed by a newline. Arrays and object keys must be deterministic as described here.

The output object schemas are exact:

parse.json has integer counts only:
{"sheets":number,"cells":number,"formulas":number,"names":number,"edits":number}
The cells count is the number of cells loaded from the input sheet cells objects before edits are applied. Cells created only by edits do not increase this count. The formulas count is the size of the final formula registry after all edits, so an edit-created formula does increase formulas.

formulas.json wraps sorted formula rows:
{"formulas":[{"cell":"Sheet!A1","formula":"=..."}]}

deps.json wraps sorted dependency rows. The wrapper key is deps and each row uses depends_on:
{"deps":[{"cell":"Sheet!A1","depends_on":["Sheet!A2"]}]}

order.json is:
{"order":["Sheet!A1"],"cycles":["Sheet!B1"]}

values.json is:
{"values":{"Sheet!A1":123}}

errors.json is:
{"errors":[{"cell":"Sheet!A1","error":"#VALUE"}]}

recalculation.json wraps edit rows under edits. Each row uses the edit id as id and does not include a cell field:
{"edits":[{"id":"edit-id","changed":["Sheet!A1"],"recomputed":["Sheet!A1","Sheet!A2"]}]}

lineage.json is:
{"lineage":[{"cell":"Sheet!A1","direct":["Sheet!A2"],"transitive":["Sheet!B1"]}]}

audit.json is:
{"audit":[{"cell":"Sheet!A1","state":"value","value":123}]}

metrics.json is:
{"max_direct_dependencies":number,"max_transitive_dependencies":number,"numeric_formula_sum":number,"text_formula_count":number,"checksum":number}

summary.json is:
{"formulas":number,"dependencies":number,"cycles":number,"errors":number,"edits":number,"lineage_edges":number}
The `dependencies` number is the total dependency edge count from deps.json: sum `depends_on.length` for every row in the `deps` array. It is not the number of dependency rows and not the number of formula cells that have at least one dependency.

Formula timing is intentionally split. The formula registry used by parse.json formula count, formulas.json, lineage.json row coverage, audit.json, metrics.json, and summary.json is the final registry after all edits. If an edit changes a cell to a formula, that cell is included in those final formula counts and rows. The dependency graph in deps.json and the cycle/order graph are built from the formulas present in the original workbook before edits. A formula introduced by an edit therefore appears in final formula-facing stages with an empty dependency list unless it was already a formula before edits. For example, if an edit creates Calc!Z1 with =SUM(MainBlock), formulas.json includes Calc!Z1, but deps.json uses {"cell":"Calc!Z1","depends_on":[]} and Calc!Z1 is not added to order.json or cycles.

References may be unqualified A1, qualified Sheet!A1, ranges A1:B3 or Sheet!A1:B3, or names from the names object. A name expands to its target before dependency output and before function evaluation. The name itself is never emitted as a dependency. When a token exactly matches a key in the names object, treat it as a name before trying to classify it as an A1-style cell reference; this is required for names such as R3, Tail4, and TAIL4 that can collide with broad cell-reference regular expressions. For example, with {"Tail":"S!A2:A4"}, =SUM(Tail) depends on ["S!A2","S!A3","S!A4"], not ["S!Tail"]. With {"R3":"S!A1:A2"}, =SUM(R3) depends on ["S!A1","S!A2"], not ["S!R3"]. Unknown symbolic names are ignored. Ranges expand row-major into individual qualified cell ids. Function names IF, SUM, MIN, MAX, and COUNT are not dependencies. Dependency arrays are unique and lexicographically sorted. Dependency rows are sorted by cell.

order.json contains DFS topological post-order for non-cyclic original formula cells. Visit formula cells lexicographically, recursively visit formula dependencies, and append after dependencies. Do not sort order after traversal. cycles contains original formula cells participating in graph cycles, sorted lexicographically.

Evaluation uses final edited cell values. Supported formulas include arithmetic operators, comparisons used by IF, IF(condition,true,false), SUM, MIN, MAX, COUNT, cell references, ranges, and named ranges. Error tokens are #CYCLE, #DIV0, and #VALUE. Original graph cycle cells evaluate as #CYCLE. Division by zero evaluates as #DIV0. A self-referential formula introduced by an edit is not part of the pre-edit cycle graph; it evaluates as #VALUE if evaluation recursively refers to itself. Any formula that cannot be evaluated numerically where numeric evaluation is required also becomes #VALUE.

values.json contains every final cell value keyed by qualified cell id, sorted lexicographically. errors.json contains one row per final error cell sorted by cell. recalculation.json has one row per edit in input order; changed is the sorted list of final cells whose value changed compared with the previous evaluation state, and recomputed is the full sorted final value-map key list for that edit.

lineage.json has one row per final formula cell sorted by cell. direct is the deps.json dependency list for that cell or [] for an edit-introduced formula with no pre-edit graph row. transitive contains reachable formula dependencies through formula-to-formula graph edges, sorted lexicographically. This reachability is across qualified cell ids and must work across sheets, not just within the source cell's sheet. summary.json lineage_edges is the total number of transitive lineage edges, not the number of direct dependency rows. audit.json has one row per final formula cell with state cycle for #CYCLE, error for other error tokens, otherwise value, and value equal to the final evaluated value.

metrics.json contains max_direct_dependencies, max_transitive_dependencies, numeric_formula_sum, text_formula_count, and checksum. numeric_formula_sum sums final numeric values for formula cells only. text_formula_count counts formula cells whose final value is a non-error string. checksum starts at 0 over sorted final formula cells; for each character of cell=value set checksum = (checksum * 131 + codepoint) mod 1000000007. The value text is the final scalar value text used by the engine: integer-typed results are written without a trailing .0, but floating-point results keep their decimal form even when mathematically integral, such as 923.0. Raw strings and error tokens are used without JSON quotes. summary.json contains formulas, dependencies, cycles, errors, edits, and lineage_edges in that order; `dependencies` is the total `depends_on` edge sum from deps.json.
