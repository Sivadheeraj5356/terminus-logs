function sample_aquifer_params(cfg, k) {
  return {
    vx: cfg.vx_mean,
    vy: cfg.vy_mean,
    alphaL: cfg.alphaL_mean,
    alphaT: cfg.alphaT_mean,
    lambda: cfg.lambda_mean,
    Dm: cfg.Dm,
    rho_b: cfg.rho_b,
    Kd: cfg.Kd,
    theta: cfg.theta,
  };
}

module.exports = { sample_aquifer_params };
