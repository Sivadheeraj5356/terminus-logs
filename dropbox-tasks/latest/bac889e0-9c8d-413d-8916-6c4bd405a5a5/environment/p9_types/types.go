package p9_types

type ChronologyRow struct {
	Seq      int    `json:"seq"`
	PatchID  string `json:"patch_id"`
	ISOWeek  string `json:"iso_week"`
}

type EraSpan struct {
	ID         int    `json:"id"`
	StartPatch string `json:"start_patch"`
	EndPatch   string `json:"end_patch"`
}

type EraOut struct {
	ID               int     `json:"id"`
	StartPatch       string  `json:"start_patch"`
	EndPatch         string  `json:"end_patch"`
	DominantActor    string  `json:"dominant_actor"`
	DiversityIndex   float64 `json:"diversity_index"`
	DominantWinLower float64 `json:"dominant_win_lower"`
}

type TurningPoint struct {
	PatchID    string  `json:"patch_id"`
	ShiftScore float64 `json:"shift_score"`
}

type Recommendation struct {
	Actor         string `json:"actor"`
	Priority      int    `json:"priority"`
	RationaleTag  string `json:"rationale_tag"`
}

type Archive struct {
	SchemaVersion  int              `json:"schema_version"`
	Scenario       string           `json:"scenario"`
	Eras           []EraOut         `json:"eras"`
	TurningPoints  []TurningPoint   `json:"turning_points"`
	Recommendations []Recommendation `json:"recommendations"`
	ArchiveDigest  string           `json:"archive_digest"`
}

type Scenario struct {
	Name        string   `json:"name"`
	Chronology  string   `json:"chronology"`
	Matches     string   `json:"matches"`
	Notes       string   `json:"notes"`
	Roster      []string `json:"roster"`
}

type MatchRow struct {
	PatchID string `json:"patch_id"`
	Actor   string `json:"actor"`
	Picks   int    `json:"picks"`
	Wins    int    `json:"wins"`
}

type NoteRow struct {
	PatchID   string `json:"patch_id"`
	Headline  string `json:"headline"`
	StatDelta int    `json:"stat_delta"`
}

type Policy struct {
	EraGapSeq        int     `json:"era_gap_seq"`
	WilsonZ          float64 `json:"wilson_z"`
	JSTurnThreshold  float64 `json:"js_turn_threshold"`
}
