Run the harden CLI from `/app`:

```text
php /app/environment/scripts/run_harden_cli.php --profile embedserve-default --out /app/out/harden_report.json
```

Requires `cargo`, `cargo-audit`, and PHP sqlite3 extension. Advisory DB path is fixed in `config/profiles.json`.
