package pond

// Plan is the active pond metadata bundle.
type Plan struct {
	PondID            string         `json:"pond_id"`
	MastEpoch         uint32         `json:"mast_epoch"`
	SectorTable       map[int]string `json:"sector_table"`
	MastBearingOffset float64        `json:"mast_bearing_offset"`
	CalmWindow        [2]int         `json:"calm_window"`
	CalmThresholdKn   float64        `json:"calm_threshold_kn"`
	MinMastEpoch      uint32         `json:"min_mast_epoch"`
	SurveyLayer       string         `json:"survey_layer"`
}
