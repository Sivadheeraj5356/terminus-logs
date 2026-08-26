# Database Schema

## agents

| Column   | Type | Constraints                            |
|----------|------|----------------------------------------|
| agent_id | TEXT | PRIMARY KEY                            |
| name     | TEXT | NOT NULL                               |
| tier     | TEXT | NOT NULL, CHECK(tier IN ('L1','L2','L3')) |

## tickets

| Column           | Type | Constraints                                                          |
|------------------|------|----------------------------------------------------------------------|
| ticket_id        | TEXT | PRIMARY KEY                                                          |
| title            | TEXT | NOT NULL                                                             |
| priority         | TEXT | NOT NULL, CHECK(priority IN ('low','medium','high','critical'))       |
| status           | TEXT | NOT NULL, DEFAULT 'open'                                             |
| assigned_agent_id| TEXT | (nullable)                                                           |
| opened_at        | TEXT | NOT NULL, DEFAULT (datetime('now'))                                  |

## resolutions

| Column            | Type    | Constraints                      |
|-------------------|---------|----------------------------------|
| resolution_id     | INTEGER | PRIMARY KEY AUTOINCREMENT        |
| ticket_id         | TEXT    | NOT NULL                         |
| agent_id          | TEXT    | NOT NULL                         |
| resolution_minutes| INTEGER | NOT NULL                         |
| sla_met           | INTEGER | NOT NULL (0=false, 1=true)       |
| resolved_at       | TEXT    | NOT NULL                         |

## resolution_chain

| Column            | Type    | Constraints               |
|-------------------|---------|---------------------------|
| chain_id          | INTEGER | PRIMARY KEY AUTOINCREMENT |
| ticket_id         | TEXT    | NOT NULL                  |
| agent_id          | TEXT    | NOT NULL                  |
| resolution_minutes| INTEGER | NOT NULL                  |
| sla_met           | TEXT    | NOT NULL ('true'/'false') |
| resolved_at       | TEXT    | NOT NULL                  |
| prev_hash         | TEXT    | NOT NULL                  |
| current_hash      | TEXT    | NOT NULL                  |

### Notes

- `resolutions.sla_met` stores 0 or 1 (integer).
- `resolution_chain.sla_met` stores the string `"true"` or `"false"` (used in HMAC data string).
- `opened_at` and `resolved_at` are ISO-8601 UTC datetime strings (SQLite `datetime('now')` format: `YYYY-MM-DD HH:MM:SS`).
