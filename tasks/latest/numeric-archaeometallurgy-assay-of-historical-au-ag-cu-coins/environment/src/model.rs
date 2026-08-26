use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Deserialize)]
pub struct AssayConfig {
    pub schema_version: u32,
    pub grid_n: usize,
    pub k_sigma: f64,
    pub default_enrichment_model_id: String,
}

#[derive(Debug, Clone, Deserialize)]
pub struct MetalDensities {
    pub schema_version: u32,
    pub rho_au: f64,
    pub rho_ag: f64,
    pub rho_cu: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EnrichmentModel {
    pub model_id: String,
    pub burial_years: f64,
    pub rate_per_year: f64,
    pub enrichment_cap: f64,
}

#[derive(Debug, Clone, Deserialize)]
pub struct EnrichmentTable {
    pub schema_version: u32,
    pub models: Vec<EnrichmentModel>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CoinInput {
    pub coin_id: String,
    pub mixing_rule: String,
    pub kappa: Option<f64>,
    pub enrichment_model_id: String,
    pub density: Option<f64>,
    pub density_sigma: Option<f64>,
    pub xrf_au: Option<f64>,
    pub xrf_ag: Option<f64>,
    pub xrf_cu: Option<f64>,
    pub xrf_sigma: Option<f64>,
}

#[derive(Debug, Clone, Deserialize)]
pub struct CoinCatalog {
    pub schema_version: u32,
    pub coins: Vec<CoinInput>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct RegionBounds {
    pub f_au_min: f64,
    pub f_au_max: f64,
    pub f_ag_min: f64,
    pub f_ag_max: f64,
    pub f_cu_min: f64,
    pub f_cu_max: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct XrfBound {
    pub f_au_min: f64,
    pub f_au_max: f64,
    pub f_ag_min: f64,
    pub f_ag_max: f64,
    pub f_cu_min: f64,
    pub f_cu_max: f64,
    pub delta: f64,
    pub model_id: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct DensityBandSummary {
    pub point_count: usize,
    pub f_au_min: f64,
    pub f_au_max: f64,
    pub f_ag_min: f64,
    pub f_ag_max: f64,
    pub f_cu_min: f64,
    pub f_cu_max: f64,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CoinRecord {
    pub coin_id: String,
    pub status: String,
    pub reason: Option<String>,
    pub mixing_rule: String,
    pub enrichment_model_id: String,
    pub density_band: Option<DensityBandSummary>,
    pub xrf_bound: Option<XrfBound>,
    pub feasible_region: Option<RegionBounds>,
    pub intersection_point_count: usize,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AssayBundle {
    pub schema_version: u32,
    pub ingest_seq: u64,
    pub assay_bind: String,
    pub config_canon_sha: String,
    pub coins: Vec<CoinRecord>,
}

pub fn round6(x: f64) -> f64 {
    (x * 1_000_000.0).round() / 1_000_000.0
}
