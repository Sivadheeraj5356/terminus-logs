use std::fs;

use crate::config::Config;
use crate::Result;

pub async fn connect(cfg: &Config) -> Result<tokio_postgres::Client> {
    let (client, conn) = tokio_postgres::connect(&cfg.dsn, tokio_postgres::NoTls).await?;
    tokio::spawn(async move {
        let _ = conn.await;
    });
    Ok(client)
}

/// Applies migrations/*.sql in name order. Every statement is idempotent.
pub async fn migrate(cfg: &Config) -> Result<()> {
    let client = connect(cfg).await?;
    let mut files: Vec<_> = fs::read_dir(&cfg.migrations)?
        .collect::<std::result::Result<Vec<_>, _>>()?
        .into_iter()
        .map(|e| e.path())
        .filter(|p| p.extension().map(|x| x == "sql").unwrap_or(false))
        .collect();
    files.sort();
    for f in files {
        let sql = fs::read_to_string(&f)?;
        client.batch_execute(&sql).await
            .map_err(|e| format!("{}: {e}", f.display()))?;
    }
    Ok(())
}
