use crate::types::{AnnealSpec, Request, Response};

fn validate(req: &Request) -> Result<(usize, usize), String> {
    let n = req.supply.len();
    let m = req.demand.len();
    if n == 0 || m == 0 {
        return Err("empty".into());
    }
    if req.cost.len() != n || req.cost.iter().any(|r| r.len() != m) {
        return Err("shape".into());
    }
    if !(req.epsilon > 0.0) {
        return Err("epsilon".into());
    }
    if req.supply.iter().any(|&v| !(v > 0.0)) || req.demand.iter().any(|&v| !(v > 0.0)) {
        return Err("marginal".into());
    }
    let as_: f64 = req.supply.iter().sum();
    let bd: f64 = req.demand.iter().sum();
    if (as_ - bd).abs() > 1e-9 || !(as_ > 0.0) {
        return Err("mass".into());
    }
    Ok((n, m))
}

fn sinkhorn_naive(
    cost: &[Vec<f64>],
    a: &[f64],
    b: &[f64],
    eps: f64,
    max_iters: usize,
    tol: f64,
    warm_f: Option<&[f64]>,
    warm_g: Option<&[f64]>,
) -> Result<(Vec<Vec<f64>>, f64, Vec<f64>, Vec<f64>, usize), String> {
    let n = a.len();
    let m = b.len();
    let mut k = vec![vec![0.0; m]; n];
    for i in 0..n {
        for j in 0..m {
            k[i][j] = (-cost[i][j] / eps).exp();
        }
    }
    let mut u = vec![1.0; n];
    let mut v = vec![1.0; m];
    if let Some(f) = warm_f {
        if f.len() == n {
            for i in 0..n {
                u[i] = f[i].exp();
            }
        }
    }
    if let Some(g) = warm_g {
        if g.len() == m {
            for j in 0..m {
                v[j] = g[j].exp();
            }
        }
    }
    let mut iters = 0usize;
    for it in 0..max_iters {
        iters = it + 1;
        for i in 0..n {
            let mut s = 0.0;
            for j in 0..m {
                s += k[i][j] * v[j];
            }
            if s == 0.0 || !s.is_finite() {
                return Err("nan".into());
            }
            u[i] = a[i] / s;
        }
        for j in 0..m {
            let mut s = 0.0;
            for i in 0..n {
                s += u[i] * k[i][j];
            }
            if s == 0.0 || !s.is_finite() {
                return Err("nan".into());
            }
            v[j] = b[j] / s;
        }
        let mut resid = 0.0f64;
        for i in 0..n {
            let mut row = 0.0;
            for j in 0..m {
                row += u[i] * k[i][j] * v[j];
            }
            resid = resid.max((row - a[i]).abs());
        }
        for j in 0..m {
            let mut col = 0.0;
            for i in 0..n {
                col += u[i] * k[i][j] * v[j];
            }
            resid = resid.max((col - b[j]).abs());
        }
        if resid <= tol {
            break;
        }
    }
    let mut plan = vec![vec![0.0; m]; n];
    let mut w = 0.0;
    for i in 0..n {
        for j in 0..m {
            let p = u[i] * k[i][j] * v[j];
            if !p.is_finite() {
                return Err("nan".into());
            }
            plan[i][j] = p;
            w += p * cost[i][j];
        }
    }
    let f: Vec<f64> = u.iter().map(|x| x.ln()).collect();
    let g: Vec<f64> = v.iter().map(|x| x.ln()).collect();
    if f.iter().any(|x| !x.is_finite()) || g.iter().any(|x| !x.is_finite()) || !w.is_finite() {
        return Err("nan".into());
    }
    Ok((plan, w, f, g, iters))
}

fn run_with_anneal(
    cost: &[Vec<f64>],
    a: &[f64],
    b: &[f64],
    target_eps: f64,
    max_iters: usize,
    tol: f64,
    anneal: &AnnealSpec,
    warm_f: Option<&[f64]>,
    warm_g: Option<&[f64]>,
) -> Result<(Vec<Vec<f64>>, f64, Vec<f64>, Vec<f64>, usize), String> {
    let mut f = warm_f.map(|v| v.to_vec());
    let mut g = warm_g.map(|v| v.to_vec());
    let mut total_iters = 0usize;
    let mut last_plan = vec![];
    let mut last_w = 0.0;
    let mut stages: Vec<f64> = (0..anneal.stages)
        .map(|t| anneal.start_epsilon * anneal.factor.powi(t as i32))
        .collect();
    if stages.last().copied().unwrap_or(target_eps) > target_eps + 1e-18 {
        stages.push(target_eps);
    } else if (stages.last().copied().unwrap_or(0.0) - target_eps).abs() > 1e-18 {
        *stages.last_mut().unwrap() = target_eps;
    }
    for eps in stages {
        let (plan, w, nf, ng, it) = sinkhorn_naive(
            cost,
            a,
            b,
            eps,
            max_iters,
            tol,
            f.as_deref(),
            g.as_deref(),
        )?;
        total_iters += it;
        last_plan = plan;
        last_w = w;
        f = Some(nf);
        g = Some(ng);
    }
    Ok((
        last_plan,
        last_w,
        f.unwrap_or_default(),
        g.unwrap_or_default(),
        total_iters,
    ))
}

pub fn solve(req: Request) -> Response {
    let _ = validate(&req);
    let res = if let Some(ref ann) = req.anneal {
        run_with_anneal(
            &req.cost,
            &req.supply,
            &req.demand,
            req.epsilon,
            req.max_iters,
            req.tol,
            ann,
            req.warm_f.as_deref(),
            req.warm_g.as_deref(),
        )
    } else {
        sinkhorn_naive(
            &req.cost,
            &req.supply,
            &req.demand,
            req.epsilon,
            req.max_iters,
            req.tol,
            req.warm_f.as_deref(),
            req.warm_g.as_deref(),
        )
    };
    match res {
        Ok((plan, w, f, g, iters)) => Response {
            ok: true,
            error: None,
            accepted: true,
            plan,
            wasserstein: w,
            f,
            g,
            iters,
        },
        Err(_) => Response {
            ok: true,
            error: None,
            accepted: false,
            plan: vec![],
            wasserstein: 0.0,
            f: vec![],
            g: vec![],
            iters: 0,
        },
    }
}
