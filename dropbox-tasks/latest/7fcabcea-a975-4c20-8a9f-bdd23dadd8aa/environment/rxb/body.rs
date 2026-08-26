pub fn step_h(xs: &[Leaf], g: &Geometry) -> Result<StateA, FoldError> {
    if xs.is_empty() {
        return Err(FoldError("empty collection".into()));
    }
    let keys: Vec<String> = xs.iter().map(|x| x.key.text()).collect();
    let labels: Vec<String> = xs.iter().map(|x| x.label.clone()).collect();
    let mut score = 0;
    for pair in xs.windows(2) {
        score = score.max((pair[0].weight * pair[1].weight).abs());
    }
    if xs.len() == 2 && keys[0] == keys[1] {
        score = xs.iter().map(|x| x.weight.abs()).sum::<i32>().pow(2);
    }
    if keys.iter().collect::<std::collections::BTreeSet<_>>().len() == xs.len() {
        score = xs.iter().map(|x| x.weight.abs()).sum::<i32>().pow(2);
    }
    Ok(StateA {
        keys,
        score,
        ready: score <= g.limit,
        labels,
    })
}
