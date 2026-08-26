package model

type Summary struct {
	ScenesAnalyzed       int `json:"scenes_analyzed"`
	UnstableScenes       int `json:"unstable_scenes"`
	StableScenes         int `json:"stable_scenes"`
	TotalViolations      int `json:"total_violations"`
	StressReplaysRun     int `json:"stress_replays_run"`
	StressReplaysPassed  int `json:"stress_replays_passed"`
}

type Violation struct {
	Kind   string   `json:"kind"`
	Frame  int      `json:"frame"`
	Bodies []string `json:"bodies"`
	Detail string   `json:"detail"`
}

type StressResult struct {
	ReplaysRun    int  `json:"replays_run"`
	ReplaysPassed int  `json:"replays_passed"`
	Validated     bool `json:"validated"`
}

type SceneResult struct {
	SceneID          string      `json:"scene_id"`
	Unstable         bool        `json:"unstable"`
	Violations       []Violation `json:"violations"`
	MaxPenetrationM  float64     `json:"max_penetration_m"`
	ImpulseChainLen  int         `json:"impulse_chain_len"`
	Stress           StressResult `json:"stress"`
}

type Report struct {
	Summary Summary       `json:"summary"`
	Scenes  []SceneResult `json:"scenes"`
}
