change history of the fee book

2026 01 01 initial publish of airframe_rates with three body codes. base and per minute differ across NB, WB, and RJ. the table is kept under feebook/airframe_rates.toml.

2026 02 14 small wording correction in gate_handbook. no rate change.

2026 03 03 added the apron_glossary file. no schema change.

2026 04 09 added the boundary note line to feebook/offhours_window.toml so the asymmetry at the start and end is unambiguous on inspection.

2026 05 01 rate refresh on all three body codes. the effective_from string on each new row is 2026 05 01 at midnight zulu. the older rows are retained because cycles that started before that minute still price under the older table.

2026 05 10 published cycle_codex with the formal verdict ladder including the holdover override on capped overage and the asymmetric duplicate handling around mtow_tons.

2026 06 02 documented the precedence behaviour on cycles that present both a duplicate and a holdover by emphasising that duplicate void is decided first on mtow disagreement regardless of status.

2026 06 19 documented that the cap counts holdover billing toward the cumulative total so a chain of holdover plus normal cycles can still trigger capped overage on subsequent normal cycles.
