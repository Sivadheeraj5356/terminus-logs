use anyhow::{bail, Result};
use clap::{Parser, Subcommand};
use ldacore::{
    config, corpus, engine, ingest, model, publication, read_json, snapshot, stable_bytes,
    write_if_changed,
};

#[derive(Parser)]
struct Cli {
    #[command(subcommand)]
    command: Command,
}

#[derive(Subcommand)]
enum Command {
    Ingest,
    Sample,
    Export,
    Status,
}

fn main() -> Result<()> {
    let cli = Cli::parse();
    let cfg = config::load()?;
    match cli.command {
        Command::Ingest => {
            let docs = ingest::read_documents(&cfg.inbox)?;
            let staging = corpus::build(docs)?;
            write_if_changed(&cfg.corpus_staging, &stable_bytes(&staging)?)?;
        }
        Command::Sample => {
            if !cfg.corpus_staging.is_file() {
                bail!("corpus staging snapshot missing");
            }
            let staging: model::CorpusStaging = read_json(&cfg.corpus_staging)?;
            let counts = engine::run(&staging, &cfg);
            write_if_changed(&cfg.count_staging, &stable_bytes(&counts)?)?;
        }
        Command::Export => {
            if !cfg.corpus_staging.is_file() || !cfg.count_staging.is_file() {
                bail!("state snapshot missing");
            }
            let corpus_bytes = std::fs::read(&cfg.corpus_staging)?;
            let count_bytes = std::fs::read(&cfg.count_staging)?;
            let rollup = publication::build(&corpus_bytes, &count_bytes, &cfg)?;
            write_if_changed(&cfg.output, &stable_bytes(&rollup)?)?;
        }
        Command::Status => {
            let staging: model::CorpusStaging = read_json(&cfg.corpus_staging)?;
            let (retained, checksum) = if cfg.count_staging.is_file() {
                let counts: model::CountStaging = read_json(&cfg.count_staging)?;
                let corpus_bytes = std::fs::read(&cfg.corpus_staging)?;
                let count_bytes = std::fs::read(&cfg.count_staging)?;
                (
                    counts.retained_sweeps.to_string(),
                    snapshot::checksum(&corpus_bytes, &count_bytes),
                )
            } else {
                ("pending".to_string(), "pending".to_string())
            };
            println!(
                "docs={} vocab={} retained_sweeps={} snapshot_checksum={}",
                staging.docs.len(),
                staging.vocab.len(),
                retained,
                checksum
            );
        }
    }
    Ok(())
}
