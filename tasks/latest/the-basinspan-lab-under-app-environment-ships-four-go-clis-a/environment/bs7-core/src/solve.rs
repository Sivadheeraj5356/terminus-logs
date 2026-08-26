use sha2::{Digest, Sha256};

use crate::correlate::correlation_matrix;
use crate::forward::{average_models, hidden_activations, mse};
use crate::merge::merge_with_alignment;
use crate::propagate::{align_model_b, hungarian};
use crate::types::{SolveIn, SolveOut, TraceRow};

fn digest_line(line: &str) -> String {
    let mut h = Sha256::new();
    h.update(line.as_bytes());
    hex::encode(h.finalize())
}

pub fn solve(input: SolveIn) -> SolveOut {
    let hidden = input.arch.hidden_dims.len();
    let mut perms = Vec::new();
    let mut trace = Vec::new();
    let mut align_cost = 0.0;

    for li in 0..hidden {
        let _acts_a = hidden_activations(&input.model_a, &input.align_samples, li);
        let _acts_b = hidden_activations(&input.model_b, &input.align_samples, li);
        let c = correlation_matrix(&input.model_a, &input.model_b, li);
        let d = c.len();
        let cost: Vec<Vec<f64>> = (0..d)
            .map(|i| (0..d).map(|j| 1.0 - c[i][j].max(0.0)).collect())
            .collect();
        let perm = hungarian(&cost);
        for i in 0..d {
            let j = perm[i];
            align_cost += cost[i][j];
            trace.push(TraceRow {
                layer: li,
                neuron_a: i,
                neuron_b: j,
                correlation: c[i][j],
                assignment_cost: cost[i][j],
            });
        }
        perms.push(perm);
    }

    let aligned = align_model_b(&input.model_b, &perms);
    let merged = merge_with_alignment(&input.model_a, &aligned, input.merge_weight);
    let naive = average_models(&input.model_a, &input.model_b, input.merge_weight);
    let eval_mse = mse(&merged, &input.model_a, &input.eval_samples);
    let naive_mse = mse(&naive, &input.model_a, &input.eval_samples);
    let barrier_value = naive_mse - eval_mse;
    let perm_str: String = perms
        .iter()
        .map(|p| p.iter().map(|x| x.to_string()).collect::<Vec<_>>().join(","))
        .collect::<Vec<_>>()
        .join(";");
    let line = format!(
        "layers={hidden}|mse={eval_mse:.6}|cost={align_cost:.6}|perms={perm_str}"
    );
    SolveOut {
        ok: true,
        align_cost,
        eval_mse,
        naive_mse,
        barrier_value,
        permutations: perms,
        trace,
        merge_digest_hex: digest_line(&line),
    }
}
