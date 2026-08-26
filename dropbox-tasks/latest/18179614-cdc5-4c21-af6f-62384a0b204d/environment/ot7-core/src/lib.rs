pub mod sinkhorn;
pub mod types;

use sinkhorn::solve;
use types::{Request, Response};

pub fn handle(req: Request) -> Response {
    // Reject validation failures cleanly
    let n = req.supply.len();
    let m = req.demand.len();
    if n == 0
        || m == 0
        || req.cost.len() != n
        || req.cost.iter().any(|r| r.len() != m)
        || !(req.epsilon > 0.0)
        || req.supply.iter().any(|&v| !(v > 0.0))
        || req.demand.iter().any(|&v| !(v > 0.0))
    {
        return Response {
            ok: true,
            error: None,
            accepted: false,
            plan: vec![],
            wasserstein: 0.0,
            f: vec![],
            g: vec![],
            iters: 0,
        };
    }
    let as_: f64 = req.supply.iter().sum();
    let bd: f64 = req.demand.iter().sum();
    if (as_ - bd).abs() > 1e-9 {
        return Response {
            ok: true,
            error: None,
            accepted: false,
            plan: vec![],
            wasserstein: 0.0,
            f: vec![],
            g: vec![],
            iters: 0,
        };
    }
    solve(req)
}
