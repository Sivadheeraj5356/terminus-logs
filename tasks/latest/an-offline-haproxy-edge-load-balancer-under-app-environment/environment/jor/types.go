package jor

// CellSpec is one fixture cell for the active arm.
type CellSpec struct {
	ID     string `json:"id"`
	Kind   string `json:"kind"`
	Match  string `json:"match"`
	Target string `json:"target"`
	Want   string `json:"want"`
}
