# State format

boiloff-stage.json version string is boiloff-stage-v1.

Each tank entry includes tank_id, terminal_id, insulation_class, status, opening_mass_tonnes, closing_gauged_tonnes, expected_closing_tonnes, heat_leak_bog_tonnes, relief_bog_tonnes, transaction_delta_tonnes, imbalance_pct, and violations array.

opening_mass_tonnes and closing_gauged_tonnes are the raw gauged_mass_tonnes values from the earliest and latest inventory snapshots for that tank (no r3). expected_closing_tonnes, heat_leak_bog_tonnes, relief_bog_tonnes, transaction_delta_tonnes, and imbalance_pct follow /app/docs/numeric-rounding.md.

status is balanced or imbalanced.

violations may include IMBALANCE_HIGH, BOG_RATE_HIGH, or RELIEF_EXCESSIVE.

stage_hash and stage_seal follow hash-contract.md.
