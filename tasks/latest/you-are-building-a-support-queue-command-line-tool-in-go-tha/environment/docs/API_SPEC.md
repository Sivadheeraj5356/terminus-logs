# API Specification

The binary is built at `/app/app`. All commands take the database path as their first argument.

---

## init

```
app init <db>
```

Creates the SQLite database at `<db>` and all four tables if they do not already exist. Idempotent — safe to call multiple times.

**Exit 0** on success (no output required).

---

## add-agent

```
app add-agent <db> <agent_id> <name> <tier>
```

Inserts a new agent row.

- `tier` must be one of: `L1`, `L2`, `L3`

**Success output (stdout):**
```
OK agent=<agent_id>
```

**Error output (stdout, exit 1):**
- `agent already exists: <agent_id>` — duplicate `agent_id`
- `invalid tier: <tier>` — tier not in allowed set

---

## open-ticket

```
app open-ticket <db> <ticket_id> <title> <priority>
```

Inserts a new ticket row with `status = 'open'`.

- `priority` must be one of: `low`, `medium`, `high`, `critical`

**Success output (stdout):**
```
OK ticket=<ticket_id>
```

**Error output (stdout, exit 1):**
- `ticket already exists: <ticket_id>` — duplicate `ticket_id`
- `invalid priority: <priority>` — priority not in allowed set

---

## list-tickets

```
app list-tickets <db>
```

Prints all tickets, one per line. Sort order: priority DESC (critical > high > medium > low), then `opened_at` ASC, then `ticket_id` ASC. Each line is tab-separated:

```
<ticket_id>\t<status>\t<assigned_agent_id>
```

- `assigned_agent_id` is empty string if no agent has been assigned.
- Prints nothing if there are no tickets.

**Exit 0.**

---

## resolve-ticket

```
app resolve-ticket <db> <ticket_id> <agent_id>
```

Resolves an open ticket.

**Validation (stdout, exit 1):**
1. `ticket not found: <ticket_id>` — ticket does not exist
2. `ticket already resolved: <ticket_id>` — ticket status is not 'open'
3. `agent not found: <agent_id>` — agent does not exist

**Resolution logic:**
- Sets ticket `status = 'resolved'` and `assigned_agent_id = <agent_id>`.
- Computes `resolution_minutes = floor(elapsed_seconds / 60)` where elapsed is `resolved_at - opened_at`.
- Checks SLA compliance: critical ≤ 60 min, high ≤ 240 min, medium ≤ 1440 min, low ≤ 4320 min.
- Appends one row to `resolutions` and one row to `resolution_chain`.

**Success output (stdout):**
```
OK resolved ticket=<ticket_id> sla_met=<true|false>
```

---

## priority-report

```
app priority-report <db>
```

Computes SLA breach statistics grouped by ticket priority.

**Output (exactly 4 lines, stdout, exit 0), in semantic order `critical`, `high`, `medium`, `low` — always all four, even if a priority has zero resolutions:**
```
<priority> total=<N> breached=<M> breach_rate=<value 4dp> sla_margin_avg=<value 2dp>
```

- `total` = count of rows in the `resolutions` table joined to `tickets` of that priority. This counts **resolved** tickets only — a ticket that is still `open` contributes nothing to `total` for its priority, regardless of how many open tickets exist.
- `breached` = count of those resolution rows where `sla_met` is false (SLA was not met).
- `breach_rate` = `breached / total`, expressed on a **0–1 scale** (a plain decimal fraction — NOT multiplied by 100, NOT a percentage). For example, 1 breach out of 3 resolutions is `0.3333`, not `33.3333`.
  - `breach_rate` is formatted to exactly 4 decimal places using **HALF_UP rounding** (round half away from zero on the 5th decimal digit), not round-half-to-even ("banker's rounding") and not truncation. For example, `1/32 = 0.03125` rounds HALF_UP to `0.0313` (the 5th decimal digit is exactly 5, so it always rounds up) — a naive `%.4f`-style float format that falls back to round-half-to-even could incorrectly produce `0.0312`, which is wrong.
  - If `total` is zero, `breach_rate` is `0.0000` (do not divide by zero).
- `sla_margin_avg` = mean of `(sla_threshold_minutes - resolution_minutes)` across only that priority's resolutions where `sla_met` is true. Breached resolutions are excluded from both the sum and the count entirely — they are not folded in as a zero or negative margin.
  - Formatted to exactly 2 decimal places using **CEILING rounding** (always round toward positive infinity, i.e. up, whenever there is any nonzero remainder at all — not just when the remainder is at or past the halfway point). This is a fourth distinct rounding convention: unlike HALF_UP above, a value like `0.801` still rounds up to `0.81` under CEILING even though HALF_UP would round it down to `0.80`.
  - If there are zero SLA-met resolutions for that priority (including when `total` is zero), `sla_margin_avg` is `0.00`.

---

## agent-stats

```
app agent-stats <db>
```

Computes per-agent resolution statistics. Uses a LEFT JOIN so agents with zero resolutions still appear.

**Output (one line per agent, stdout, exit 0):**
```
<agent_id> tier=<tier> resolved=<N> avg_minutes=<value 4dp> breaches=<B> queue_digest=<8 hex chars>
```

- `resolved` = count of rows in `resolutions` for that agent.
- `avg_minutes` = mean of `resolution_minutes` across that agent's resolutions, using floating-point division, formatted to 4 decimal places. **Agents with zero resolutions print `avg_minutes=0.0000`** (not blank, not an error, not omitted).
- `breaches` = count of that agent's resolutions where `sla_met` is false.
- `queue_digest` = the first 8 characters of the lowercase hex `HMAC-SHA256` of `<agent_id>:<comma-joined resolved ticket_ids sorted ascending>`, using the same key as `resolution_chain` (`HMAC_SECRET` env var, falling back to `support-queue-secret-2026` — see chain-spec.md). This is computed fresh from the current `resolutions.ticket_id` rows for that agent at query time, not read back from any stored column. An agent with zero resolutions still gets a digest (the HMAC of `<agent_id>:` with an empty ticket-id list, not a blank field).

**Sort order:** `resolved` descending, then `avg_minutes` ascending, then `agent_id` ascending.

---

## priority-stats

```
app priority-stats <db>
```

Prints a TSV table of per-priority resolution statistics, one row per priority that has at least one resolution (priorities with zero resolutions are omitted entirely — this differs from `priority-report`, which always shows all four).

**Output (header line, then one row per distinct resolved priority sorted alphabetically, stdout, exit 0):**
```
priority	resolution_count	avg_resolution_minutes	stddev_resolution	p75_resolution_minutes
```

- Sort order is **alphabetical** by priority name (`critical`, `high`, `low`, `medium`), NOT severity order.
- `resolution_count` = count of resolutions for that priority.
- `avg_resolution_minutes` = mean of `resolution_minutes`, formatted to 2 decimal places using **HALF_EVEN ("banker's") rounding**.
- `stddev_resolution` = population standard deviation (divide by N), formatted to 4 decimal places.
- `p75_resolution_minutes` = nearest-rank P75 (`ceil(0.75 × n)`, 1-indexed), formatted to 4 decimal places.
- If there are zero resolutions in the whole database, only the header line is printed (no data rows).

---

## chain-verify

```
app chain-verify <db>
```

Verifies the integrity of the global HMAC-SHA256 audit chain.

**Output on clean chain (stdout, exit 0):**
```
OK
```

**Output on tampered chain (stdout, exit 1):**
```
TAMPERED <chain_id>
```
One line per tampered row. All rows are checked before exiting.

---

## sla-report

```
app sla-report <db>
```

Computes SLA and resolution-time statistics.

**Output (7 lines, stdout, exit 0):**
```
total_tickets=<N>
sla_met_pct=<value 4dp>
p50_resolution_minutes=<value>
p75_resolution_minutes=<value>
p95_resolution_minutes=<value>
std_resolution=<value 4dp>
avg_resolution_minutes=<value 4dp>
```

- `total_tickets` = count of all rows in `tickets` table.
- `sla_met_pct` = (rows in resolutions where sla_met=1) / (total rows in resolutions) × 100, formatted to 4 decimal places; 0.0000 if no resolutions.
- Percentiles use nearest-rank method over `resolution_minutes` values from `resolutions` table.
- `std_resolution` = population standard deviation of `resolution_minutes`, formatted to 4 decimal places; 0.0000 if no resolutions.

---

## ticket-analytics

```
app ticket-analytics <db>
```

Computes sample statistics over all resolved tickets.

**Output (5 lines, stdout, exit 0):**
```
total_resolved=<N>
p25_resolution_minutes=<value>
iqr_resolution_minutes=<value>
sample_std_resolution=<value 4dp>
cv_resolution=<value 4dp>
```

- `total_resolved` = count of all rows in `resolutions` table.
- `p25_resolution_minutes` = nearest-rank P25 (ceil(0.25 × n), 1-indexed), output as integer.
- `iqr_resolution_minutes` = P75 minus P25 (nearest-rank), output as integer.
- `sample_std_resolution` = Bessel-corrected standard deviation (divide by N-1); output `0.0000` if n ≤ 1.
- `cv_resolution` = (sample_std / mean) × 100 to 4 decimal places; output `0.0000` if mean is 0 or no resolutions.

---

## workload-balance

```
app workload-balance <db>
```

Computes per-agent workload utilization based on currently open tickets.

**Tier capacity constants (open tickets per agent):**
- `L1`: 5
- `L2`: 15
- `L3`: 30

**Utilization:** `(count of OPEN tickets assigned to agent) / capacity × 100`, formatted to 4 decimal places.

- An "open ticket assigned to agent" means a ticket with `status = 'open'` AND `assigned_agent_id = <agent_id>`.
- All agents are shown, including those with zero open assigned tickets (utilization = 0.0000).

**Output (one line per agent, stdout, exit 0):**
```
<agent_id> tier=<tier> open=<N> utilization=<value 4dp>
```

**Sort order:** utilization descending, then agent_id ascending.

**Exit 0** even if no agents exist (empty output).

---

## dispersion-report

```
app dispersion-report <db>
```

Computes median and median-absolute-deviation statistics over `resolution_minutes` across all rows in the `resolutions` table (same scope as `ticket-analytics`).

**Output (4 lines, stdout, exit 0):**
```
n=<N>
median_resolution_minutes=<value>
mad_resolution_minutes=<value 4dp>
mad_normalized=<value 4dp>
```

- `n` = count of resolutions (integer).
- `median_resolution_minutes` uses the nearest-rank formula (see statistics-spec.md), output as an integer — not the average-of-two-middle-values definition.
- `mad_resolution_minutes` and `mad_normalized` — see statistics-spec.md for the exact two-pass derivation and the `1.4826` constant.
- If there are zero resolutions: `n=0`, `median_resolution_minutes=0`, `mad_resolution_minutes=0.0000`, `mad_normalized=0.0000`.

---

## escalation-audit

```
app escalation-audit <db>
```

Lists currently-open tickets whose time-in-queue has breached escalation thresholds relative to their priority's SLA window (the same SLA minutes as `resolve-ticket`: critical=60, high=240, medium=1440, low=4320). Resolved tickets are never considered.

Capture the current time with a single `datetime('now')` read at the start of the command and reuse that same value for every open ticket being evaluated — do not re-read the current time per ticket.

- `elapsed_minutes` = `floor(elapsed_seconds / 60)` between the captured "now" and the ticket's `opened_at`, clamped to a minimum of 0 (same floor-division convention as `resolution_minutes` in `resolve-ticket`).
- `ratio` = `elapsed_minutes / threshold` (floating-point division), where `threshold` is that ticket's priority SLA minutes.
- Band lookup (boundaries below are inclusive on the lower side, mirroring `resolve-ticket`'s `<=` SLA-met convention — a ticket exactly on a boundary belongs to the band it has just entered, not the one before):
  - `ratio <= 1.0` → `on_track` (never printed)
  - `1.0 < ratio <= 2.0` → `at_risk`
  - `2.0 < ratio <= 4.0` → `escalated`
  - `ratio > 4.0` → `critical_escalation`

**Output (one line per breached open ticket, stdout, exit 0):**
```
<ticket_id>\tpriority=<priority>\tband=<band>\telapsed_minutes=<N>\tthreshold=<T>\tratio=<value 4dp>
```
(tab-separated fields)

- Only tickets in `at_risk`, `escalated`, or `critical_escalation` are printed; `on_track` tickets are omitted entirely (there is no all-bands-always requirement here, unlike `priority-report`).
- **Sort order:** band severity **descending** using the fixed rank `critical_escalation`(3) > `escalated`(2) > `at_risk`(1) — this is NOT alphabetical (compare to `priority-stats`, which IS alphabetical) — then `elapsed_minutes` descending, then `ticket_id` ascending.
- `ratio` = `elapsed_minutes / threshold`, formatted to exactly 4 decimal places using **truncation toward zero** — the dropped digits are simply cut off, never rounded up. This is a third rounding convention, distinct from `priority-report`'s HALF_UP and `priority-stats`' HALF_EVEN. For example `157/60 = 2.616666...` truncates to `2.6166`, not `2.6167` (which is what HALF_UP would produce).
- **Exit 0** always. Prints nothing if there are no open tickets or none have breached `at_risk`.

---

## queue-lint

```
app queue-lint <db>
```

Runs six fixed-order domain integrity rules against the current database
state and reports violations for each. See `/docs/lint-spec.md` for the
exact rule order, rule definitions, and output contract.

**Exit 0** if all six rules pass (`OVERALL PASS`), **exit 1** if any rule
fails (`OVERALL FAIL`).
