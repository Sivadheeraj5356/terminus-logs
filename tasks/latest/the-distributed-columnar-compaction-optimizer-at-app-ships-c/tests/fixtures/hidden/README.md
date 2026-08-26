Verifier-only CLFC catalog definitions (not shipped in the agent image).

tests/seed_hidden_catalogs.py writes HIDDEN_CATALOGS from fixture_data.py into
/opt/verifier-fixtures/catalogs when tests/test.sh runs, before pytest.
Keys: gap_chain, tie_break, strict_overlap, row_wrap, null_byte_col, replica_strict_fail, export_shadow, poison_norm_tie.
