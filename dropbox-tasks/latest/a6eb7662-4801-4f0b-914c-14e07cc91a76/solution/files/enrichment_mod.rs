use crate::model::{AssayConfig, EnrichmentModel, EnrichmentTable, XrfBound, round6};

pub fn lookup_model<'a>(
    table: &'a EnrichmentTable,
    model_id: &str,
    _cfg: &AssayConfig,
) -> Result<&'a EnrichmentModel, String> {
    table
        .models
        .iter()
        .find(|m| m.model_id == model_id)
        .ok_or_else(|| format!("unknown enrichment model {model_id}"))
}

pub fn enrichment_delta(model: &EnrichmentModel) -> f64 {
    (model.rate_per_year * model.burial_years).min(model.enrichment_cap)
}

pub fn corrected_xrf_bound(
    f_au_s: f64,
    f_ag_s: f64,
    f_cu_s: f64,
    sigma: f64,
    model: &EnrichmentModel,
    cfg: &AssayConfig,
) -> XrfBound {
    let delta = enrichment_delta(model);
    let ks = cfg.k_sigma * sigma;
    // Directional silver-bloom / copper-depletion bounds.
    XrfBound {
        f_au_min: round6((f_au_s - delta - ks).max(0.0)),
        f_au_max: round6((f_au_s + ks).min(1.0)),
        f_ag_min: round6((f_ag_s - delta - ks).max(0.0)),
        f_ag_max: round6((f_ag_s + ks).min(1.0)),
        f_cu_min: round6((f_cu_s - ks).max(0.0)),
        f_cu_max: round6((f_cu_s + delta + ks).min(1.0)),
        delta: round6(delta),
        model_id: model.model_id.clone(),
    }
}

pub fn point_in_xrf_bound(a: f64, g: f64, c: f64, b: &XrfBound) -> bool {
    a >= b.f_au_min - 1e-12
        && a <= b.f_au_max + 1e-12
        && g >= b.f_ag_min - 1e-12
        && g <= b.f_ag_max + 1e-12
        && c >= b.f_cu_min - 1e-12
        && c <= b.f_cu_max + 1e-12
}
