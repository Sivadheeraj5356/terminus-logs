use anyhow::{bail, Context, Result};
use rusqlite::{params, Connection};
use std::env;
use std::path::PathBuf;

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
    let conn = Connection::open(db_path)?;
    create_schema(&conn)?;
    load_placeholder(&conn, input_path.to_string_lossy().as_ref())?;
    Ok(())
}

fn create_schema(conn: &Connection) -> Result<()> {
    conn.execute_batch(
        "CREATE TABLE IF NOT EXISTS employee_history (
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
            recorded_at TEXT NOT NULL
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

fn load_placeholder(conn: &Connection, source_file: &str) -> Result<()> {
    conn.execute(
        "INSERT INTO load_audit(source_file, accepted_count, rejected_count) VALUES (?1, 0, 0)",
        params![source_file],
    )?;
    Ok(())
}
