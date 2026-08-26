use anyhow::{bail, Result};
use serde::Deserialize;
use std::path::PathBuf;

#[derive(Deserialize)]
struct Raw {
    inbox: String,
    corpus_staging: String,
    count_staging: String,
    output: String,
    topics: usize,
    alpha: f64,
    beta: f64,
    sweeps: usize,
    burn_in: usize,
    seed: u64,
    top_terms: usize,
}

pub struct Config {
    pub inbox: PathBuf,
    pub corpus_staging: PathBuf,
    pub count_staging: PathBuf,
    pub output: PathBuf,
    pub k: usize,
    pub alpha: f64,
    pub beta: f64,
    pub sweeps: usize,
    pub burn_in: usize,
    pub seed: u64,
    pub top_terms: usize,
}

pub fn load() -> Result<Config> {
    let text = std::fs::read_to_string("/app/config/ldactl.toml")?;
    let raw: Raw = toml::from_str(&text)?;
    let configured = PathBuf::from(&raw.inbox);
    let inbox = match std::env::var("TB3_LDA_ROOT") {
        Ok(value) if PathBuf::from(&value).is_absolute() => PathBuf::from(value),
        _ => configured,
    };
    if !inbox.is_absolute() {
        bail!("inbox must be absolute");
    }
    if raw.topics == 0 {
        bail!("topics must be positive");
    }
    if raw.top_terms == 0 {
        bail!("top_terms must be positive");
    }
    if raw.sweeps <= raw.burn_in {
        bail!("sweeps must exceed burn_in");
    }
    Ok(Config {
        inbox,
        corpus_staging: PathBuf::from(raw.corpus_staging),
        count_staging: PathBuf::from(raw.count_staging),
        output: PathBuf::from(raw.output),
        k: raw.topics,
        alpha: raw.alpha,
        beta: raw.beta,
        sweeps: raw.sweeps,
        burn_in: raw.burn_in,
        seed: raw.seed,
        top_terms: raw.top_terms,
    })
}
