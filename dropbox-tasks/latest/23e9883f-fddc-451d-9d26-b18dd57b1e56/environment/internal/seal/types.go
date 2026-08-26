package seal

type ModeCell struct {
	PanelID  string
	Family   string
	Mode     string
	Locale   string
	OmegaObs float64
	OmegaRef float64
	Excit    float64
}

type FamilyBound struct {
	Lo           float64 `json:"lo"`
	Hi           float64 `json:"hi"`
	MaxTightness float64 `json:"max_tightness"`
}

type LocalePick struct {
	Weight     float64
	Generation uint64
	Source     string
}

type LocaleBundle struct {
	Locales    map[string]LocalePick
	Mismatched []string
	Agreement  bool
	PeelSource string
	Epoch      uint64
}

type PanelScore struct {
	BoundViolations int     `json:"bound_violations"`
	Tightness        float64 `json:"tightness"`
	MaxTightness     float64 `json:"max_tightness"`
	Family           string  `json:"family"`
}

type ScoreArm struct {
	Digest          string
	TotalViolations int
	MaxTightness    float64
	Panels          map[string]PanelScore
}
