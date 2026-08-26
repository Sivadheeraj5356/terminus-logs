use crate::density;
use crate::enrichment;
use crate::intersect;
use crate::model::{
    AssayBundle, AssayConfig, CoinCatalog, CoinInput, CoinRecord, EnrichmentTable, MetalDensities,
};
use std::fs;
use std::path::Path;

pub fn load_json<T: serde::de::DeserializeOwned>(path: &Path) -> Result<T, String> {
    let raw = fs::read_to_string(path).map_err(|e| format!("{}: {e}", path.display()))?;
    serde_json::from_str(&raw).map_err(|e| format!("{}: {e}", path.display()))
}

pub fn evaluate_coin(
    coin: &CoinInput,
    metals: &MetalDensities,
    models: &EnrichmentTable,
    cfg: &AssayConfig,
) -> CoinRecord {
    let mut rec = CoinRecord {
        coin_id: coin.coin_id.clone(),
        status: "insufficient_data".to_string(),
        reason: None,
        mixing_rule: coin.mixing_rule.clone(),
        enrichment_model_id: coin.enrichment_model_id.clone(),
        density_band: None,
        xrf_bound: None,
        feasible_region: None,
        intersection_point_count: 0,
    };

    let (Some(rho_m), Some(sig_rho)) = (coin.density, coin.density_sigma) else {
        rec.reason = Some("missing_density".to_string());
        return rec;
    };

    let band_pts = match density::density_band_points(
        rho_m,
        sig_rho,
        &coin.mixing_rule,
        coin.kappa,
        metals,
        cfg.grid_n,
    ) {
        Ok(p) => p,
        Err(_) => {
            rec.status = "insufficient_data".to_string();
            rec.reason = Some("missing_density".to_string());
            return rec;
        }
    };
    rec.density_band = density::summarize_points(&band_pts);

    let xrf_complete = coin.xrf_au.is_some()
        && coin.xrf_ag.is_some()
        && coin.xrf_cu.is_some()
        && coin.xrf_sigma.is_some();

    if !xrf_complete {
        let f_au = coin.xrf_au.unwrap_or(0.0);
        let f_ag = coin.xrf_ag.unwrap_or(0.0);
        let f_cu = coin.xrf_cu.unwrap_or(0.0);
        let sig = coin.xrf_sigma.unwrap_or(0.0);
        if coin.xrf_au.is_none() && coin.xrf_ag.is_none() && coin.xrf_cu.is_none() {
            if coin.xrf_sigma.is_none() {
                let model = match enrichment::lookup_model(models, &coin.enrichment_model_id, cfg) {
                    Ok(m) => m,
                    Err(e) => {
                        rec.reason = Some(e);
                        return rec;
                    }
                };
                let bound = enrichment::corrected_xrf_bound(f_au, f_ag, f_cu, sig, model, cfg);
                rec.xrf_bound = Some(bound.clone());
                let (hit, region) = intersect::intersect_region(&band_pts, &bound);
                rec.intersection_point_count = hit.len();
                if let Some(r) = region {
                    rec.status = "feasible".to_string();
                    rec.feasible_region = Some(r);
                } else {
                    rec.status = "inconsistent".to_string();
                    rec.reason = Some("empty_intersection".to_string());
                }
                return rec;
            }
        }
        if coin.xrf_au.is_some() && coin.xrf_sigma.is_none() {
            rec.reason = Some("missing_xrf_uncertainty".to_string());
            return rec;
        }
    }

    let f_au = coin.xrf_au.unwrap_or(0.0);
    let f_ag = coin.xrf_ag.unwrap_or(0.0);
    let f_cu = coin.xrf_cu.unwrap_or(0.0);
    let Some(sig) = coin.xrf_sigma else {
        rec.reason = Some("missing_xrf_uncertainty".to_string());
        return rec;
    };

    let model = match enrichment::lookup_model(models, &coin.enrichment_model_id, cfg) {
        Ok(m) => m,
        Err(e) => {
            rec.reason = Some(e);
            return rec;
        }
    };
    let bound = enrichment::corrected_xrf_bound(f_au, f_ag, f_cu, sig, model, cfg);
    rec.xrf_bound = Some(bound.clone());
    let (hit, region) = intersect::intersect_region(&band_pts, &bound);
    rec.intersection_point_count = hit.len();
    if let Some(r) = region {
        rec.status = "feasible".to_string();
        rec.feasible_region = Some(r);
        rec.reason = None;
    } else {
        rec.status = "inconsistent".to_string();
        rec.reason = Some("empty_intersection".to_string());
    }
    rec
}

pub fn build_bundle(
    cfg_path: &Path,
    coins_path: &Path,
    metals_path: &Path,
    models_path: &Path,
) -> Result<AssayBundle, String> {
    let cfg: AssayConfig = load_json(cfg_path)?;
    let catalog: CoinCatalog = load_json(coins_path)?;
    let metals: MetalDensities = load_json(metals_path)?;
    let models: EnrichmentTable = load_json(models_path)?;

    let mut coins: Vec<CoinRecord> = catalog
        .coins
        .iter()
        .map(|c| evaluate_coin(c, &metals, &models, &cfg))
        .collect();
    coins.sort_by(|a, b| a.coin_id.cmp(&b.coin_id));

    Ok(AssayBundle {
        schema_version: 1,
        ingest_seq: 0,
        assay_bind: String::new(),
        config_canon_sha: String::new(),
        coins,
    })
}
