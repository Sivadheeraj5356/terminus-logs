use crate::model::Unit;

pub fn order(units: &[Unit]) -> Vec<String> {
    let mut ids: Vec<&Unit> = units.iter().collect();
    ids.sort_by(|a, b| a.speed.cmp(&b.speed).then_with(|| a.id.cmp(&b.id)));
    ids.into_iter().map(|u| u.id.clone()).collect()
}
