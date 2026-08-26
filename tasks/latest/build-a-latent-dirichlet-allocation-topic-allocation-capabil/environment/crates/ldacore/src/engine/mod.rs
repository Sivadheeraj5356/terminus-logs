use crate::config::Config;
use crate::ledger;
use crate::model::{CorpusStaging, CountStaging};
use crate::retention;
use crate::rng;
use crate::sampler;

pub fn run(corpus: &CorpusStaging, cfg: &Config) -> CountStaging {
    let k = cfg.k;
    let v = corpus.vocab.len();
    let d = corpus.docs.len();

    let mut n_dk = vec![vec![0u64; k]; d];
    let mut n_kw = vec![vec![0u64; v]; k];
    let mut n_k = vec![0u64; k];
    let mut theta_sum = vec![vec![0.0f64; k]; d];
    let mut assignments: Vec<Vec<usize>> = Vec::with_capacity(d);

    let mut state = rng::seed_state(cfg.seed);
    let mut token_index = 0usize;
    for (di, doc) in corpus.docs.iter().enumerate() {
        let mut row = Vec::with_capacity(doc.token_ids.len());
        for &w in &doc.token_ids {
            let topic = rng::init_topic(&mut state, k, token_index);
            ledger::add(&mut n_dk, &mut n_kw, &mut n_k, di, topic, w);
            row.push(topic);
            token_index += 1;
        }
        assignments.push(row);
    }

    for sweep in 1..=cfg.sweeps {
        for di in 0..d {
            for i in 0..assignments[di].len() {
                let w = corpus.docs[di].token_ids[i];
                let old = assignments[di][i];
                ledger::remove(&mut n_dk, &mut n_kw, &mut n_k, di, old, w);
                let mut masses = vec![0.0f64; k];
                let mut total = 0.0f64;
                for topic in 0..k {
                    let mass = sampler::conditional(
                        n_dk[di][topic],
                        n_kw[topic][w],
                        n_k[topic],
                        cfg.alpha,
                        cfg.beta,
                        v,
                    );
                    masses[topic] = mass;
                    total += mass;
                }
                let draw = rng::uniform(&mut state) * total;
                let new = sampler::choose(&masses, draw);
                ledger::add(&mut n_dk, &mut n_kw, &mut n_k, di, new, w);
                assignments[di][i] = new;
            }
        }
        if retention::should_accumulate(sweep, cfg.burn_in) {
            retention::accumulate(&mut theta_sum, &n_dk, cfg.alpha, k);
        }
    }

    let retained_sweeps = retention::retained_count(cfg.sweeps, cfg.burn_in);

    CountStaging {
        schema: "lda-counts/v1".into(),
        k,
        alpha: cfg.alpha,
        beta: cfg.beta,
        seed: cfg.seed,
        sweeps: cfg.sweeps,
        burn_in: cfg.burn_in,
        retained_sweeps,
        vocab: corpus.vocab.clone(),
        doc_ids: corpus.docs.iter().map(|doc| doc.doc_id.clone()).collect(),
        assignments,
        n_dk,
        n_kw,
        n_k,
        theta_sum,
    }
}
