use crate::config::Config;
use crate::model::{CorpusStaging, CountStaging, DocTheta, Rollup, TopicRollup};
use crate::ranking;
use crate::snapshot;
use anyhow::Result;

pub fn build(corpus_bytes: &[u8], count_bytes: &[u8], cfg: &Config) -> Result<Rollup> {
    let _corpus: CorpusStaging = serde_json::from_slice(corpus_bytes)?;
    let counts: CountStaging = serde_json::from_slice(count_bytes)?;

    let mut topics = Vec::with_capacity(counts.k);
    for topic in 0..counts.k {
        let top_terms = ranking::top_terms(
            &counts.n_kw[topic],
            counts.n_k[topic],
            &counts.vocab,
            counts.beta,
            cfg.top_terms,
        );
        topics.push(TopicRollup { topic, top_terms });
    }
    topics.reverse();

    let retained = counts.retained_sweeps as f64;
    let mut documents = Vec::with_capacity(counts.doc_ids.len());
    for (d, doc_id) in counts.doc_ids.iter().enumerate() {
        let theta: Vec<f64> = counts.theta_sum[d].iter().map(|s| s / retained).collect();
        documents.push(DocTheta {
            doc_id: doc_id.clone(),
            theta,
        });
    }
    documents.reverse();

    let checksum = snapshot::checksum(count_bytes, corpus_bytes);

    Ok(Rollup {
        schema: "lda-rollup/v1".into(),
        retained_sweeps: counts.retained_sweeps,
        topics,
        documents,
        snapshot_checksum: checksum,
    })
}
