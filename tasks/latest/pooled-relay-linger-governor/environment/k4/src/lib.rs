use rusqlite::{params, Connection};
use std::path::Path;
use thiserror::Error;

#[derive(Debug, Clone)]
pub struct ReclaimRow {
    pub socket_id: u32,
    pub shard: u32,
    pub event: String,
    pub pool_generation: u32,
    pub round_index: u32,
}

#[derive(Debug, Error)]
pub enum StoreError {
    #[error("sqlite: {0}")]
    Sql(#[from] rusqlite::Error),
    #[error("workload mismatch")]
    WorkloadMismatch,
}

pub struct Store {
    conn: Connection,
}

impl Store {
    pub fn open(path: &Path) -> Result<Self, StoreError> {
        if let Some(parent) = path.parent() {
            std::fs::create_dir_all(parent).ok();
        }
        let conn = Connection::open(path)?;
        conn.execute_batch(
            "CREATE TABLE IF NOT EXISTS run_meta (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                workload_id TEXT NOT NULL DEFAULT '',
                pool_generation INTEGER NOT NULL DEFAULT 0,
                governance_ready INTEGER NOT NULL DEFAULT 0,
                phase_cursor TEXT NOT NULL DEFAULT ''
            );
            CREATE TABLE IF NOT EXISTS reclaim_events (
                socket_id INTEGER NOT NULL,
                shard INTEGER NOT NULL,
                event TEXT NOT NULL,
                pool_generation INTEGER NOT NULL,
                round_index INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS generation_seals (
                pool_generation INTEGER PRIMARY KEY,
                sealed INTEGER NOT NULL DEFAULT 0
            );",
        )?;
        conn.execute(
            "INSERT INTO run_meta (id) VALUES (1) ON CONFLICT(id) DO NOTHING",
            [],
        )?;
        Ok(Self { conn })
    }

    pub fn begin_run(&mut self, workload_id: &str) -> Result<(u32, bool), StoreError> {
        let (stored, gen, ready): (String, i32, i32) = self.conn.query_row(
            "SELECT workload_id, pool_generation, governance_ready FROM run_meta WHERE id = 1",
            [],
            |row| Ok((row.get(0)?, row.get(1)?, row.get(2)?)),
        )?;
        if stored.is_empty() {
            self.conn.execute(
                "UPDATE run_meta SET workload_id = ?1 WHERE id = 1",
                params![workload_id],
            )?;
            return Ok((0, false));
        }
        if stored != workload_id {
            return Err(StoreError::WorkloadMismatch);
        }
        Ok((gen as u32, ready != 0))
    }

    pub fn pool_generation(&self) -> Result<u32, StoreError> {
        let gen: i32 = self
            .conn
            .query_row("SELECT pool_generation FROM run_meta WHERE id = 1", [], |r| r.get(0))?;
        Ok(gen as u32)
    }

    pub fn governance_ready(&self) -> Result<bool, StoreError> {
        let ready: i32 = self.conn.query_row(
            "SELECT governance_ready FROM run_meta WHERE id = 1",
            [],
            |r| r.get(0),
        )?;
        Ok(ready != 0)
    }

    pub fn mark_populated(&mut self) -> Result<u32, StoreError> {
        self.conn.execute(
            "UPDATE run_meta SET governance_ready = 1, pool_generation = pool_generation + 1 WHERE id = 1",
            [],
        )?;
        self.pool_generation()
    }

    pub fn persist_d(&mut self, row: &ReclaimRow) -> Result<(), StoreError> {
        self.conn.execute(
            "INSERT INTO reclaim_events (socket_id, shard, event, pool_generation, round_index)
             VALUES (?1, ?2, ?3, ?4, ?5)",
            params![
                row.socket_id,
                row.shard,
                row.event,
                row.pool_generation,
                row.round_index,
            ],
        )?;
        Ok(())
    }

    pub fn list_reclaims(&self) -> Result<Vec<ReclaimRow>, StoreError> {
        let mut stmt = self.conn.prepare(
            "SELECT socket_id, shard, event, pool_generation, round_index
             FROM reclaim_events ORDER BY round_index ASC, socket_id ASC",
        )?;
        let rows = stmt
            .query_map([], |row| {
                Ok(ReclaimRow {
                    socket_id: row.get(0)?,
                    shard: row.get(1)?,
                    event: row.get(2)?,
                    pool_generation: row.get(3)?,
                    round_index: row.get(4)?,
                })
            })?
            .collect::<Result<Vec<_>, _>>()?;
        Ok(rows)
    }

    pub fn state_bytes(&self, path: &Path) -> u64 {
        std::fs::metadata(path).map(|m| m.len()).unwrap_or(0)
    }

    pub fn seal_generation(&mut self, _gen: u32) -> Result<(), StoreError> {
        Ok(())
    }

    pub fn is_generation_sealed(&self, _gen: u32) -> Result<bool, StoreError> {
        Ok(true)
    }
}
