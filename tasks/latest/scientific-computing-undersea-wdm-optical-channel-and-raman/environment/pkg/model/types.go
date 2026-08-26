package model

type Node struct {
	ID    string `json:"id"`
	Regen bool   `json:"regen"`
}

type Span struct {
	ID       string `json:"id"`
	A        string `json:"a"`
	B        string `json:"b"`
	CapGbps  int    `json:"cap_gbps"`
	PumpMW   float64 `json:"pump_mw"`
	Lambdas  []int  `json:"lambdas"`
}

type Demand struct {
	ID       string `json:"id"`
	Src      string `json:"src"`
	Dst      string `json:"dst"`
	Gbps     int    `json:"gbps"`
	Priority int    `json:"priority"`
	PeerA    string `json:"peer_a"`
	PeerB    string `json:"peer_b"`
}

type Scenario struct {
	ScenarioID   string   `json:"scenario_id"`
	CoolFactor   float64  `json:"cool_factor"`
	MwPerChannel float64  `json:"mw_per_channel"`
	Nodes        []Node   `json:"nodes"`
	Spans        []Span   `json:"spans"`
	Cuts         []string `json:"cuts"`
	Demands      []Demand `json:"demands"`
}

type Hop struct {
	DemandID string `json:"demand_id"`
	Hop      int    `json:"hop"`
	SpanID   string `json:"span_id"`
	Lambda   int    `json:"lambda"`
	Gbps     int    `json:"gbps"`
}

type Report struct {
	ScenarioID      string   `json:"scenario_id"`
	Served          []string `json:"served"`
	Rejected        []string `json:"rejected"`
	TotalGbps       int      `json:"total_gbps"`
	PumpPeakMW      float64  `json:"pump_peak_mw"`
	SettleScore     float64  `json:"settle_score"`
	Feasible        bool     `json:"feasible"`
	Generation      int      `json:"generation"`
	PriorDigestHex  string   `json:"prior_digest_hex"`
	DigestHex       string   `json:"digest_hex"`
}
