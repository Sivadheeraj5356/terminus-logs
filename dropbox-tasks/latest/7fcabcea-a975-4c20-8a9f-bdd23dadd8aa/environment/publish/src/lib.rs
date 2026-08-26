pub mod render;

use manifest::{Leaf, Request};

pub fn execute(req: &Request) -> Result<(), String> {
    let leaves: Vec<Leaf> = req
        .entries
        .iter()
        .map(|x| {
            catalog::phase_c(x, &req.registry)
                .map(|key| Leaf {
                    label: x.label.clone(),
                    key,
                    weight: x.weight,
                })
                .map_err(|e| e.to_string())
        })
        .collect::<Result<_, _>>()?;
    let state = algebra::step_h(&leaves, &req.geometry).map_err(|e| e.to_string())?;
    let frame = store::commit(
        &state,
        &req.meta,
        &req.scope,
        &req.state_dir,
        req.replay_latest,
    )?;
    render::write(&frame)
}
