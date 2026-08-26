# Offline MLflow tracking-store subset

The fixture is a normal SQLite representation of the MLflow entities needed by
Maze League. Column order is not significant. Implementations should query by
column name and must tolerate unrelated columns and unrelated MLflow rows.

```sql
experiments(experiment_id INTEGER PRIMARY KEY, name TEXT, lifecycle_stage TEXT)
runs(run_uuid TEXT PRIMARY KEY, experiment_id INTEGER, status TEXT,
     lifecycle_stage TEXT, start_time INTEGER, end_time INTEGER)
params(run_uuid TEXT, key TEXT, value TEXT)
metrics(run_uuid TEXT, key TEXT, value REAL, timestamp INTEGER, step INTEGER)
tags(run_uuid TEXT, key TEXT, value TEXT)
```

MLflow permits metric history and repeated tag or parameter rows in imported
stores, even though its service normally constrains some of them. The recovery
contract therefore defines duplicate handling explicitly. Run UUIDs and values
are opaque text; SQL parameters must be bound rather than interpolated.
