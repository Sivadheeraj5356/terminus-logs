package tape

// Row is one line from the wind observation tape.
type Row struct {
	Day         int     `json:"day"`
	Tick        int     `json:"tick"`
	DirDeg      float64 `json:"dir_deg"`
	SpeedKn     float64 `json:"speed_kn"`
	TelemetryOK bool    `json:"telemetry_ok"`
}
