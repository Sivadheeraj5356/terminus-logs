use crate::model::TopTerm;

pub fn top_terms(
    n_kw_row: &[u64],
    n_k_topic: u64,
    vocab: &[String],
    beta: f64,
    top_terms: usize,
) -> Vec<TopTerm> {
    let _ = beta;
    let denom = n_k_topic as f64;
    let mut items: Vec<(String, u64, f64)> = vocab
        .iter()
        .enumerate()
        .map(|(w, token)| {
            let probability = if denom > 0.0 {
                n_kw_row[w] as f64 / denom
            } else {
                0.0
            };
            (token.clone(), n_kw_row[w], probability)
        })
        .collect();
    items.sort_by(|a, b| b.1.cmp(&a.1).then(b.0.cmp(&a.0)));
    items
        .into_iter()
        .take(top_terms)
        .map(|(token, _, probability)| TopTerm { token, probability })
        .collect()
}
