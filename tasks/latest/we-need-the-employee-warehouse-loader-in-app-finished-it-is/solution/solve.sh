#!/bin/bash
set -euo pipefail

cd /app
cat > /app/src/main.rs <<'RS'
use anyhow::{anyhow, bail, Context, Result};
use csv::StringRecord;
use rusqlite::{params, Connection};
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::collections::BTreeMap;
use std::env;
use std::fs;
use std::path::{Path, PathBuf};

#[derive(Clone)]
struct Event {
    event_key: String,
    source_file: String,
    line_number: i64,
    batch_id: String,
    source_system: String,
    employee_id: String,
    full_name: String,
    department: String,
    title: String,
    manager_id: Option<String>,
    location: String,
    annual_salary: i64,
    status: String,
    attrs_json: String,
    valid_from: String,
    recorded_at: String,
    operation: String,
    correction_id: String,
    row_hash: String,
}

fn main() -> Result<()> {
    let mut args = env::args().skip(1);
    let Some(command) = args.next() else {
        bail!("expected ingest command");
    };
    if command != "ingest" {
        bail!("unknown command: {command}");
    }

    let mut db_path: Option<PathBuf> = None;
    let mut input_path: Option<PathBuf> = None;
    while let Some(arg) = args.next() {
        match arg.as_str() {
            "--db" => db_path = args.next().map(PathBuf::from),
            "--input" => input_path = args.next().map(PathBuf::from),
            other => bail!("unknown argument: {other}"),
        }
    }

    let db_path = db_path.context("--db is required")?;
    let input_path = input_path.context("--input is required")?;
    let mut conn = Connection::open(db_path)?;
    create_schema(&conn)?;
    let files = discover_inputs(&input_path)?;
    let tx = conn.transaction()?;
    for file in files {
        process_file(&tx, &file)?;
    }
    rebuild_history(&tx)?;
    tx.commit()?;
    Ok(())
}

fn create_schema(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS employee_events (
            event_key TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            batch_id TEXT NOT NULL,
            source_system TEXT NOT NULL,
            employee_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            title TEXT NOT NULL,
            manager_id TEXT,
            location TEXT NOT NULL,
            annual_salary INTEGER NOT NULL,
            status TEXT NOT NULL,
            attrs_json TEXT NOT NULL,
            valid_from TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            operation TEXT NOT NULL,
            correction_id TEXT NOT NULL,
            row_hash TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS employee_history (
            employee_id TEXT NOT NULL,
            full_name TEXT NOT NULL,
            department TEXT NOT NULL,
            title TEXT NOT NULL,
            manager_id TEXT,
            location TEXT NOT NULL,
            annual_salary INTEGER NOT NULL,
            status TEXT NOT NULL,
            attrs_json TEXT NOT NULL,
            source_system TEXT NOT NULL,
            effective_start TEXT NOT NULL,
            effective_end TEXT,
            is_current INTEGER NOT NULL,
            row_hash TEXT NOT NULL,
            batch_id TEXT NOT NULL,
            correction_id TEXT NOT NULL,
            recorded_at TEXT NOT NULL,
            PRIMARY KEY(employee_id, effective_start)
        );
        CREATE TABLE IF NOT EXISTS employee_rejects (
            reject_key TEXT PRIMARY KEY,
            source_file TEXT NOT NULL,
            line_number INTEGER NOT NULL,
            employee_id TEXT,
            reason TEXT NOT NULL,
            raw_record TEXT NOT NULL,
            batch_id TEXT
        );
        CREATE TABLE IF NOT EXISTS load_audit (
            audit_id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_file TEXT NOT NULL,
            accepted_count INTEGER NOT NULL,
            rejected_count INTEGER NOT NULL
        );",
    )?;
    Ok(())
}

fn discover_inputs(input: &Path) -> Result<Vec<PathBuf>> {
    if input.is_file() {
        return Ok(vec![input.to_path_buf()]);
    }
    if !input.is_dir() {
        bail!("input path does not exist: {}", input.display());
    }
    let mut out = Vec::new();
    collect_csv(input, &mut out)?;
    out.sort();
    Ok(out)
}

fn collect_csv(dir: &Path, out: &mut Vec<PathBuf>) -> Result<()> {
    let mut entries: Vec<PathBuf> = fs::read_dir(dir)?
        .map(|entry| entry.map(|e| e.path()))
        .collect::<std::result::Result<Vec<_>, _>>()?;
    entries.sort();
    for path in entries {
        if path.is_dir() {
            collect_csv(&path, out)?;
        } else if path.extension().and_then(|e| e.to_str()) == Some("csv") {
            out.push(path);
        }
    }
    Ok(())
}

fn process_file(conn: &Connection, file: &Path) -> Result<()> {
    let mut reader = csv::ReaderBuilder::new().flexible(false).from_path(file)?;
    let headers = reader.headers()?.clone();
    let source_file = file.to_string_lossy().to_string();
    let mut accepted = 0_i64;
    let mut rejected = 0_i64;

    for (idx, rec) in reader.records().enumerate() {
        let line_number = idx as i64 + 2;
        match rec {
            Ok(record) => match parse_event(&headers, &record, &source_file, line_number) {
                Ok(event) => {
                    conn.execute(
                        "INSERT OR IGNORE INTO employee_events(
                            event_key, source_file, line_number, batch_id, source_system, employee_id,
                            full_name, department, title, manager_id, location, annual_salary, status,
                            attrs_json, valid_from, recorded_at, operation, correction_id, row_hash
                        ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17, ?18, ?19)",
                        params![
                            event.event_key,
                            event.source_file,
                            event.line_number,
                            event.batch_id,
                            event.source_system,
                            event.employee_id,
                            event.full_name,
                            event.department,
                            event.title,
                            event.manager_id,
                            event.location,
                            event.annual_salary,
                            event.status,
                            event.attrs_json,
                            event.valid_from,
                            event.recorded_at,
                            event.operation,
                            event.correction_id,
                            event.row_hash,
                        ],
                    )?;
                    accepted += 1;
                }
                Err(err) => {
                    let raw = raw_record(&headers, &record);
                    let employee_id = value(&headers, &record, "employee_id").ok().filter(|s| !s.is_empty());
                    let batch_id = value(&headers, &record, "batch_id").ok().filter(|s| !s.is_empty());
                    insert_reject(conn, &source_file, line_number, employee_id.as_deref(), &err.to_string(), &raw, batch_id.as_deref())?;
                    rejected += 1;
                }
            },
            Err(err) => {
                insert_reject(conn, &source_file, line_number, None, &err.to_string(), "", None)?;
                rejected += 1;
            }
        }
    }

    conn.execute(
        "INSERT INTO load_audit(source_file, accepted_count, rejected_count) VALUES (?1, ?2, ?3)",
        params![source_file, accepted, rejected],
    )?;
    Ok(())
}

fn parse_event(headers: &StringRecord, record: &StringRecord, source_file: &str, line_number: i64) -> Result<Event> {
    let batch_id = required(headers, record, "batch_id")?;
    let source_system = required(headers, record, "source_system")?;
    let employee_id = required(headers, record, "employee_id")?;
    let full_name = required(headers, record, "full_name")?;
    let department = required(headers, record, "department")?;
    let title = required(headers, record, "title")?;
    let manager_id = optional(headers, record, "manager_id")?;
    let location = required(headers, record, "location")?;
    let salary_text = required(headers, record, "annual_salary")?;
    let annual_salary: i64 = salary_text.parse().map_err(|_| anyhow!("annual_salary is not an integer"))?;
    if annual_salary < 0 {
        bail!("annual_salary is negative");
    }
    let mut status = required(headers, record, "status")?;
    let attrs_raw = required(headers, record, "attrs_json")?;
    let attrs_value: Value = serde_json::from_str(&attrs_raw).map_err(|_| anyhow!("attrs_json is not valid JSON"))?;
    let attrs_json = serde_json::to_string(&attrs_value)?;
    let valid_from = required(headers, record, "valid_from")?;
    validate_date(&valid_from).map_err(|e| anyhow!("valid_from {e}"))?;
    let recorded_at = required(headers, record, "recorded_at")?;
    validate_recorded_at(&recorded_at)?;
    let operation = required(headers, record, "operation")?.to_uppercase();
    if operation != "UPSERT" && operation != "DELETE" {
        bail!("operation must be UPSERT or DELETE");
    }
    if operation == "DELETE" {
        status = "terminated".to_string();
    }
    let correction_id = required(headers, record, "correction_id")?;
    let row_hash = hash_parts(&[
        &source_system,
        &full_name,
        &department,
        &title,
        manager_id.as_deref().unwrap_or(""),
        &location,
        &annual_salary.to_string(),
        &status,
        &attrs_json,
        &operation,
    ]);
    let event_key = hash_parts(&[
        source_file,
        &line_number.to_string(),
        &batch_id,
        &source_system,
        &employee_id,
        &valid_from,
        &recorded_at,
        &correction_id,
        &row_hash,
    ]);

    Ok(Event {
        event_key,
        source_file: source_file.to_string(),
        line_number,
        batch_id,
        source_system,
        employee_id,
        full_name,
        department,
        title,
        manager_id,
        location,
        annual_salary,
        status,
        attrs_json,
        valid_from,
        recorded_at,
        operation,
        correction_id,
        row_hash,
    })
}

fn rebuild_history(conn: &Connection) -> Result<()> {
    let mut stmt = conn.prepare(
        "SELECT event_key, source_file, line_number, batch_id, source_system, employee_id,
                full_name, department, title, manager_id, location, annual_salary, status,
                attrs_json, valid_from, recorded_at, operation, correction_id, row_hash
         FROM employee_events
         ORDER BY employee_id, valid_from, recorded_at, correction_id, batch_id",
    )?;
    let mut rows = stmt.query([])?;
    let mut by_employee: BTreeMap<String, BTreeMap<String, Event>> = BTreeMap::new();
    while let Some(row) = rows.next()? {
        let event = Event {
            event_key: row.get(0)?,
            source_file: row.get(1)?,
            line_number: row.get(2)?,
            batch_id: row.get(3)?,
            source_system: row.get(4)?,
            employee_id: row.get(5)?,
            full_name: row.get(6)?,
            department: row.get(7)?,
            title: row.get(8)?,
            manager_id: row.get(9)?,
            location: row.get(10)?,
            annual_salary: row.get(11)?,
            status: row.get(12)?,
            attrs_json: row.get(13)?,
            valid_from: row.get(14)?,
            recorded_at: row.get(15)?,
            operation: row.get(16)?,
            correction_id: row.get(17)?,
            row_hash: row.get(18)?,
        };
        let dates = by_employee.entry(event.employee_id.clone()).or_default();
        match dates.get(&event.valid_from) {
            Some(existing) if !is_better_correction(&event, existing) => {}
            _ => {
                dates.insert(event.valid_from.clone(), event);
            }
        }
    }

    conn.execute("DELETE FROM employee_history", [])?;
    for (_employee, dated) in by_employee {
        let mut emitted: Vec<Event> = Vec::new();
        for event in dated.into_values() {
            if emitted.last().map(|prev| same_business_state(prev, &event)).unwrap_or(false) {
                continue;
            }
            emitted.push(event);
        }
        for idx in 0..emitted.len() {
            let event = &emitted[idx];
            let effective_end = emitted.get(idx + 1).map(|next| next.valid_from.as_str());
            let is_current = if effective_end.is_none() { 1_i64 } else { 0_i64 };
            conn.execute(
                "INSERT INTO employee_history(
                    employee_id, full_name, department, title, manager_id, location,
                    annual_salary, status, attrs_json, source_system, effective_start,
                    effective_end, is_current, row_hash, batch_id, correction_id, recorded_at
                ) VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8, ?9, ?10, ?11, ?12, ?13, ?14, ?15, ?16, ?17)",
                params![
                    event.employee_id,
                    event.full_name,
                    event.department,
                    event.title,
                    event.manager_id,
                    event.location,
                    event.annual_salary,
                    event.status,
                    event.attrs_json,
                    event.source_system,
                    event.valid_from,
                    effective_end,
                    is_current,
                    event.row_hash,
                    event.batch_id,
                    event.correction_id,
                    event.recorded_at,
                ],
            )?;
        }
    }
    Ok(())
}

fn is_better_correction(candidate: &Event, existing: &Event) -> bool {
    (&candidate.recorded_at, &candidate.correction_id, &candidate.batch_id)
        > (&existing.recorded_at, &existing.correction_id, &existing.batch_id)
}

fn same_business_state(left: &Event, right: &Event) -> bool {
    left.source_system == right.source_system
        && left.full_name == right.full_name
        && left.department == right.department
        && left.title == right.title
        && left.manager_id == right.manager_id
        && left.location == right.location
        && left.annual_salary == right.annual_salary
        && left.status == right.status
        && left.attrs_json == right.attrs_json
        && left.operation == right.operation
}

fn insert_reject(
    conn: &Connection,
    source_file: &str,
    line_number: i64,
    employee_id: Option<&str>,
    reason: &str,
    raw_record: &str,
    batch_id: Option<&str>,
) -> Result<()> {
    let reject_key = hash_parts(&[source_file, &line_number.to_string(), raw_record, reason]);
    conn.execute(
        "INSERT OR IGNORE INTO employee_rejects(reject_key, source_file, line_number, employee_id, reason, raw_record, batch_id)
         VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7)",
        params![reject_key, source_file, line_number, employee_id, reason, raw_record, batch_id],
    )?;
    Ok(())
}

fn value(headers: &StringRecord, record: &StringRecord, name: &str) -> Result<String> {
    let idx = headers.iter().position(|h| h == name).with_context(|| format!("missing column {name}"))?;
    Ok(record.get(idx).unwrap_or("").trim().to_string())
}

fn required(headers: &StringRecord, record: &StringRecord, name: &str) -> Result<String> {
    let val = value(headers, record, name)?;
    if val.is_empty() {
        bail!("{name} is required");
    }
    Ok(val)
}

fn optional(headers: &StringRecord, record: &StringRecord, name: &str) -> Result<Option<String>> {
    let val = value(headers, record, name)?;
    if val.is_empty() { Ok(None) } else { Ok(Some(val)) }
}

fn raw_record(headers: &StringRecord, record: &StringRecord) -> String {
    let mut parts = Vec::new();
    for (idx, header) in headers.iter().enumerate() {
        parts.push(format!("{}={}", header, record.get(idx).unwrap_or("")));
    }
    parts.join("|")
}

fn validate_recorded_at(value: &str) -> Result<()> {
    if value.len() != 20 || &value[10..11] != "T" || &value[19..20] != "Z" {
        bail!("recorded_at is not a UTC ISO timestamp");
    }
    validate_date(&value[..10]).map_err(|e| anyhow!("recorded_at {e}"))?;
    let hour: i32 = value[11..13].parse().map_err(|_| anyhow!("recorded_at has bad hour"))?;
    let minute: i32 = value[14..16].parse().map_err(|_| anyhow!("recorded_at has bad minute"))?;
    let second: i32 = value[17..19].parse().map_err(|_| anyhow!("recorded_at has bad second"))?;
    if &value[13..14] != ":" || &value[16..17] != ":" || !(0..=23).contains(&hour) || !(0..=59).contains(&minute) || !(0..=59).contains(&second) {
        bail!("recorded_at is not a UTC ISO timestamp");
    }
    Ok(())
}

fn validate_date(value: &str) -> Result<()> {
    if value.len() != 10 || &value[4..5] != "-" || &value[7..8] != "-" {
        bail!("is not YYYY-MM-DD");
    }
    let year: i32 = value[0..4].parse().map_err(|_| anyhow!("has bad year"))?;
    let month: i32 = value[5..7].parse().map_err(|_| anyhow!("has bad month"))?;
    let day: i32 = value[8..10].parse().map_err(|_| anyhow!("has bad day"))?;
    if !(1..=12).contains(&month) {
        bail!("has bad month");
    }
    let max_day = match month {
        1 | 3 | 5 | 7 | 8 | 10 | 12 => 31,
        4 | 6 | 9 | 11 => 30,
        2 if is_leap_year(year) => 29,
        2 => 28,
        _ => unreachable!(),
    };
    if day < 1 || day > max_day {
        bail!("has bad day");
    }
    Ok(())
}

fn is_leap_year(year: i32) -> bool {
    (year % 4 == 0 && year % 100 != 0) || year % 400 == 0
}

fn hash_parts(parts: &[&str]) -> String {
    let mut hasher = Sha256::new();
    for part in parts {
        hasher.update(part.as_bytes());
        hasher.update([0]);
    }
    hex::encode(hasher.finalize())
}
RS
cargo build --quiet
