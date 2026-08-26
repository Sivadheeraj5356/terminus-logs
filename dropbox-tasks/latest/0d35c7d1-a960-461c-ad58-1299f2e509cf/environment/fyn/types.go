package fyn

// LaneRow is one composed lane entry for the active arm. A folded row may
// carry several matcher values in Match.
type LaneRow struct {
	Kind   string
	Match  []string
	Target string
	Want   string
	Mode   string
	Group  string
	Key    string
	Seq    uint64
}
