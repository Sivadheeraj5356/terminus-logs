use crate::evaluate::evaluate;
use crate::types::{CheckResult, CheckState, Counterexample, Model};

pub fn run_checks(model: &Model, states: Vec<CheckState>) -> Vec<CheckResult> {
    states
        .into_iter()
        .map(|state| {
            let base = evaluate(model, &state.point);
            let mut best: Option<Counterexample> = None;
            for feature in model.features.values() {
                if state.locked.contains(&feature.id) {
                    continue;
                }
                for value in feature.min..=feature.max {
                    let mut values = state.point.clone();
                    values.insert(feature.id.clone(), value);
                    let cost = feature.cost * (value - state.point[&feature.id]).abs();
                    if cost > state.budget {
                        continue;
                    }
                    let evaluation = evaluate(model, &values);
                    if evaluation.prediction != base.prediction {
                        best = Some(Counterexample {
                            cost,
                            changed: usize::from(value != state.point[&feature.id]),
                            values,
                            evaluation,
                        });
                        break;
                    }
                }
                if best.is_some() {
                    break;
                }
            }
            CheckResult { state, base, counterexample: best }
        })
        .collect()
}
