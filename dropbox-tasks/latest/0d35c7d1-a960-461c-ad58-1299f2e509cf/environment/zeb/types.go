package zeb

// Session holds the durable drive counters for the reload pipeline.
type Session struct {
	ActiveGen int    `json:"active_gen"`
	Floor     int    `json:"floor"`
	Anchor    string `json:"anchor"`
	Epoch     int    `json:"epoch"`
	LastArm   string `json:"last_arm"`
}
