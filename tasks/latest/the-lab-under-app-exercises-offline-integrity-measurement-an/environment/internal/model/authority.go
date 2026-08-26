package model

// AuthorityPin selects which policy index lane is live.
type AuthorityPin struct {
	Schema string `json:"schema"`
	Key    string `json:"key"`
	Ep     int    `json:"ep"`
}

// AuthorityIndex maps lane names to policy bundle paths.
type AuthorityIndex struct {
	Schema string `json:"schema"`
	Live   string `json:"live"`
	Hold   string `json:"hold"`
	Arm    string `json:"arm"`
}

// AuthorityStamp carries covenant seeds for the pin epoch.
type AuthorityStamp struct {
	Schema string `json:"schema"`
	A      int    `json:"a"`
	B      int    `json:"b"`
	C      int    `json:"c"`
}
