package report

type Anomaly struct {
	Kind      string `json:"kind"`
	PullIndex int    `json:"pull_index"`
	ItemID    string `json:"item_id"`
}

type SessionRow struct {
	SessionID     string    `json:"session_id"`
	PlayerID      string    `json:"player_id"`
	BannerID      string    `json:"banner_id"`
	Status        string    `json:"status"`
	PullsKept     int       `json:"pulls_kept"`
	PityAtStart   int       `json:"pity_at_start"`
	PityAtEnd     int       `json:"pity_at_end"`
	SeedOK        bool      `json:"seed_ok"`
	SessionDigest string    `json:"session_digest"`
	Anomalies     []Anomaly `json:"anomalies"`
	AnomalyKinds  []string  `json:"anomaly_kinds"`
}

type Summary struct {
	SessionsTotal   int     `json:"sessions_total"`
	SessionsClean   int     `json:"sessions_clean"`
	SessionsTainted int     `json:"sessions_tainted"`
	PullsTotal      int     `json:"pulls_total"`
	AnomalyCount    int     `json:"anomaly_count"`
	IntegrityScore  float64 `json:"integrity_score"`
}

type Report struct {
	Summary         Summary      `json:"summary"`
	Sessions        []SessionRow `json:"sessions"`
	CleanSessionIDs []string     `json:"clean_session_ids"`
}
