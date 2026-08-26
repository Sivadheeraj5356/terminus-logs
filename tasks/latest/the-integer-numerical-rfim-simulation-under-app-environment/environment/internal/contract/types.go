package contract

type Spin struct {
	ID        string `json:"id"`
	BiasMilli int64  `json:"bias_milli"`
	Initial   int    `json:"initial"`
}

type Edge struct {
	A             string `json:"a"`
	B             string `json:"b"`
	CouplingMilli int64  `json:"coupling_milli"`
}

type Model struct {
	Schema               string `json:"schema"`
	InitialExternalMilli int64  `json:"initial_external_milli"`
	InitialDirection     int    `json:"initial_direction"`
	Spins                []Spin `json:"spins"`
	Edges                []Edge `json:"edges"`
}

type FieldSample struct {
	Sample        int
	ExternalMilli int64
}

type RuntimeEdge struct {
	A             int
	B             int
	CouplingMilli int64
}

type RuntimeModel struct {
	Spins                []Spin
	Edges                []RuntimeEdge
	InitialExternalMilli int64
	InitialDirection     int
	Digest               string
}

type AvalancheRecord struct {
	Sample               int      `json:"sample"`
	Event                int      `json:"event"`
	Round                int      `json:"round"`
	Direction            int      `json:"direction"`
	TriggerExternalMilli int64    `json:"trigger_external_milli"`
	Flipped              []string `json:"flipped"`
	BeforeDigest         string   `json:"before_digest"`
	AfterDigest          string   `json:"after_digest"`
	EnergyBeforeMilli    int64    `json:"energy_before_milli"`
	EnergyAfterMilli     int64    `json:"energy_after_milli"`
}

type CheckpointSpin struct {
	ID    string `json:"id"`
	State int    `json:"state"`
}

type Checkpoint struct {
	Schema            string           `json:"schema"`
	ModelDigest       string           `json:"model_digest"`
	FieldDigest       string           `json:"field_digest"`
	NextSample        int              `json:"next_sample"`
	LastExternalMilli int64            `json:"last_external_milli"`
	LastDirection     int              `json:"last_direction"`
	Spins             []CheckpointSpin `json:"spins"`
	ChainDigest       string           `json:"chain_digest"`
}
