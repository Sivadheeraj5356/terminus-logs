# operators

Bake the workspace:

```bash
bash /app/environment/scripts/bake_rs.sh
```

Run one arm and band:

```bash
bash /app/environment/scripts/run_grid.sh --arm cedar --band dawn
```

Full grid:

```bash
/app/environment/bin/grti_matrix_k9 --all-arms --witness-out /app/output/rule_witness.json
```

Health probe (local only):

```bash
/app/environment/bin/grti_matrix_k9 health
```
