use crate::model::TopTerm;

pub fn top_terms(
    n_kw_row: &[u64],
    n_k_topic: u64,
    vocab: &[String],
    beta: f64,
    top_terms: usize,
) -> Vec<TopTerm> {
    let v = vocab.len();
    let denom = n_k_topic as f64 + v as f64 * beta;
    let mut items: Vec<(String, f64)> = vocab
        .iter()
        .enumerate()
        .map(|(w, token)| (token.clone(), (n_kw_row[w] as f64 + beta) / denom))
        .collect();
    items.sort_by(|a, b| {
        b.1.partial_cmp(&a.1)
            .unwrap_or(std::cmp::Ordering::Equal)
            .then(a.0.cmp(&b.0))
    });
    items
        .into_iter()
        .take(top_terms)
        .map(|(token, probability)| TopTerm { token, probability })
        .collect()
}
