use crate::model::CorpusStaging;

pub fn tfidf_preview(corpus: &CorpusStaging) -> Vec<f64> {
    let d = corpus.docs.len() as f64;
    let v = corpus.vocab.len();
    let mut document_frequency = vec![0u64; v];
    for doc in &corpus.docs {
        let mut seen = std::collections::BTreeSet::new();
        for &w in &doc.token_ids {
            seen.insert(w);
        }
        for w in seen {
            document_frequency[w] += 1;
        }
    }
    (0..v)
        .map(|w| ((1.0 + d) / (1.0 + document_frequency[w] as f64)).ln() + 1.0)
        .collect()
}
