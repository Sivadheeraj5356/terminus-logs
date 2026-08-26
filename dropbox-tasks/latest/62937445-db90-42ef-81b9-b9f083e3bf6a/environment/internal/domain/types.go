package domain

type Observation struct {
	ID         string  `json:"observation_id"`
	Run        string  `json:"run_id"`
	Peptide    string  `json:"peptide"`
	Time       float64 `json:"-"`
	Confidence float64 `json:"confidence"`
	Coordinate float64 `json:"coordinate"`
}

type Source struct {
	Path   string `json:"path"`
	SHA256 string `json:"sha256"`
	Bytes  int    `json:"bytes"`
	Rows   int    `json:"rows"`
}

type RunRecord struct {
	Run            string   `json:"run_id"`
	ObservationIDs []string `json:"observation_ids"`
	CoordinateHash string   `json:"coordinate_digest"`
}

type Center struct {
	Peptide string  `json:"peptide"`
	Value   float64 `json:"center"`
	Support int     `json:"support"`
}

type Model struct {
	TrainingRuns []string `json:"training_runs"`
	Centers      []Center `json:"centers"`
}

type Residual struct {
	ObservationID string  `json:"observation_id"`
	Peptide       string  `json:"peptide"`
	Coordinate    float64 `json:"coordinate"`
	Center        float64 `json:"center"`
	Residual      float64 `json:"residual"`
	Covered       bool    `json:"covered"`
}

type Replay struct {
	HoldoutRun   string     `json:"holdout_run"`
	TrainingRuns []string   `json:"training_runs"`
	Model        Model      `json:"model"`
	Residuals    []Residual `json:"residuals"`
	Threshold    float64    `json:"threshold"`
	QuantileRank int        `json:"quantile_rank"`
	Covered      int        `json:"covered"`
	Total        int        `json:"total"`
}

type SelectedView struct {
	HoldoutRun     string   `json:"holdout_run"`
	TrainingRuns   []string `json:"training_runs"`
	ObservationIDs []string `json:"observation_ids"`
}

type CacheEntry struct {
	Scope   string  `json:"scope"`
	Peptide string  `json:"peptide"`
	Center  float64 `json:"center"`
}

type Lineage struct {
	SelectedViews []SelectedView `json:"selected_views"`
	CacheEntries  []CacheEntry   `json:"cache_entries"`
}

type Seal struct {
	Algorithm string `json:"algorithm"`
	Digest    string `json:"digest"`
}

type Attestation struct {
	SchemaVersion  string        `json:"schema_version"`
	CoverageTarget float64       `json:"coverage_target"`
	Sources        []Source      `json:"sources"`
	Observations   []Observation `json:"observations"`
	Runs           []RunRecord   `json:"runs"`
	Model          Model         `json:"model"`
	Replays        []Replay      `json:"replays"`
	Lineage        Lineage       `json:"lineage"`
	Seal           *Seal         `json:"seal,omitempty"`
}
