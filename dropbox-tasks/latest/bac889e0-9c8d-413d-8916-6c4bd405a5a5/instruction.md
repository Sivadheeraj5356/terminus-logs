# Game balance archaeology

The live-ops desk archived years of competitive telemetry through a Go pipeline under `/app/environment`, but exports no longer line up with design reviews. Era windows look calendar-driven, actor rates disagree with match volumes, and the stamped archive seal fails audit replay.

Repair sources under `/app/environment`, rebuild with `make -C /app/environment all`, and regenerate `/app/output/balance_archive.json` through `/opt/simbin/balancectl` per `/app/environment/docs/cli_invocation.txt`. Binding formulas live in `/app/environment/docs/balance_contract.md`. The regenerated archive must follow that contract, including schema_version, scenario, eras, turning_points, recommendations, archive_digest, and era-row dominant_win_lower values. A 2019 design memo may describe the wrong calendar windowing. Validate with `/tests/test.sh`.
