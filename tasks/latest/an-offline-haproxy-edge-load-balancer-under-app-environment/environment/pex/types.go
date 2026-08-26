package pex

// CellOut is one sealed cell outcome.
type CellOut struct {
	ID      string `json:"id"`
	Outcome string `json:"outcome"`
	Target  string `json:"target"`
	Group   string `json:"group"`
}

// HopRec is one hop observation for a routed cell.
type HopRec struct {
	ID    string `json:"id"`
	Cover string `json:"cover"`
	Group string `json:"group"`
}
