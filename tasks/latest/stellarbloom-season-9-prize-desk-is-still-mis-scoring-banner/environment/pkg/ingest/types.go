package ingest

type Pull struct {
	PullIndex int    `json:"pull_index"`
	ItemID    string `json:"item_id"`
	Rarity    string `json:"rarity"`
	Receipt   string `json:"receipt"`
}

type Session struct {
	SessionID      string `json:"session_id"`
	PlayerID       string `json:"player_id"`
	BannerID       string `json:"banner_id"`
	OpenedAt       string `json:"opened_at"`
	Revision       int    `json:"revision"`
	ServerSeed     string `json:"server_seed"`
	ServerSeedHash string `json:"server_seed_hash"`
	Pulls          []Pull `json:"pulls"`
}

type Bundle struct {
	Sessions []Session `json:"sessions"`
}
