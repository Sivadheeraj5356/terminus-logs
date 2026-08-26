use crate::config::Config;
use crate::model::{CorpusStaging, CountStaging, DocTheta, Rollup, TopicRollup};
use crate::ranking;
use crate::snapshot;
use anyhow::{bail, Result};

pub fn build(corpus_bytes: &[u8], count_bytes: &[u8], cfg: &Config) -> Result<Rollup> {
    let corpus: CorpusStaging = serde_json::from_slice(corpus_bytes)?;
    let counts: CountStaging = serde_json::from_slice(count_bytes)?;

    if corpus.vocab != counts.vocab {
        bail!("vocabulary mismatch between snapshots");
    }
    let corpus_doc_ids: Vec<String> = corpus.docs.iter().map(|d| d.doc_id.clone()).collect();
    if corpus_doc_ids != counts.doc_ids {
        bail!("document order mismatch between snapshots");
    }
    if counts.k != cfg.k {
        bail!("topic count mismatch with configuration");
    }
    if counts.n_kw.len() != counts.k || counts.n_k.len() != counts.k || counts.n_dk.len() != counts.doc_ids.len() {
        bail!("count shape invalid");
    }
    if counts.retained_sweeps == 0 {
        bail!("no retained sweeps");
    }
    let v = counts.vocab.len();

    let mut topics = Vec::with_capacity(counts.k);
    for topic in 0..counts.k {
        if counts.n_kw[topic].len() != v {
            bail!("count shape invalid");
        }
        let top_terms = ranking::top_terms(
            &counts.n_kw[topic],
            counts.n_k[topic],
            &counts.vocab,
            counts.beta,
            cfg.top_terms,
        );
        topics.push(TopicRollup { topic, top_terms });
    }

    let retained = counts.retained_sweeps as f64;
    let mut documents = Vec::with_capacity(counts.doc_ids.len());
    for (d, doc_id) in counts.doc_ids.iter().enumerate() {
        let mut theta: Vec<f64> = counts.theta_sum[d].iter().map(|s| s / retained).collect();
        let sum: f64 = theta.iter().sum();
        for value in theta.iter_mut() {
            *value /= sum;
        }
        documents.push(DocTheta {
            doc_id: doc_id.clone(),
            theta,
        });
    }

    let checksum = snapshot::checksum(corpus_bytes, count_bytes);

    Ok(Rollup {
        schema: "lda-rollup/v1".into(),
        retained_sweeps: counts.retained_sweeps,
        topics,
        documents,
        snapshot_checksum: checksum,
    })
}
