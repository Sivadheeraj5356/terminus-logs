pub mod pairwise_overlap {
    //! Diagnostic-only token overlap board — not used for attribution.

    #[allow(dead_code)]
    pub fn overlap_ratio(left: &str, right: &str) -> f64 {
        if left.is_empty() && right.is_empty() {
            return 1.0;
        }
        let ls: std::collections::BTreeSet<char> = left.chars().collect();
        let rs: std::collections::BTreeSet<char> = right.chars().collect();
        let inter = ls.intersection(&rs).count() as f64;
        let union = ls.union(&rs).count() as f64;
        if union == 0.0 {
            0.0
        } else {
            inter / union
        }
    }
}

pub fn board_label() -> &'static str {
    "pairwise_overlap"
}
