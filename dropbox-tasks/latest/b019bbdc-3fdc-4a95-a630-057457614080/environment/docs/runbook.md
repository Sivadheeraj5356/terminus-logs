# Optical replan runbook

Scientific-computing operator chain for WDM channel assignment and Raman cool residuals.

```bash
export PATH="/usr/local/cargo/bin:/usr/local/go/bin:/app/bin:$PATH"
cd /app/environment/oxk && cargo build --release --locked
cp target/release/oxk-cli /app/bin/oxk-cli
cd /app/environment && go build -o /app/bin/splicectl ./cmd/splicectl

splicectl reset
splicectl run eq_pacific
splicectl run eq_cool_stress
splicectl status
splicectl publish
```

Canonical chains also exercise `eq_priority`, `eq_regen_gap`, `eq_cap_bind`, `eq_path_tie`, `eq_pump_tight`, `eq_empty_demands` (negative), and unknown ids (negative). The `eq_cap_bind` chain checks multi-hop span capacity: a single-hop demand commits first, then a two-hop demand must be rejected when a shared middle span would overflow. Cross-commit cool carry is checked by repeating `eq_cool_stress` and by interleaving a disjoint topology (`eq_pacific`) between cool commits so idle-span residuals must survive.

Before treating a fix as complete, replay the full runbook chain above (not just the opening smoke trio) and confirm served/rejected sets match independent replay of each fixture.
