pub fn seal_q(a: &StateA, _b: &InputsB, _c: &ScopeC) -> Stamp {
    let mut labels = a.labels.clone();
    labels.sort();
    Stamp {
        value: labels.join("+"),
    }
}
