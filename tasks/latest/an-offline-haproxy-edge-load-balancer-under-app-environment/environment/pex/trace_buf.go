package pex

var (
	lastHops   []HopRec
	lastPane   string
	lastTwin   string
	lastGroups []string
)

// ClearBuf resets sealed hop and digest buffers.
func ClearBuf() {
	lastHops = nil
	lastPane = ""
	lastTwin = ""
	lastGroups = nil
}

// SaveBuf stores hop records and paired digests for emit.
func SaveBuf(hops []HopRec, pane, twin string, groups []string) {
	lastHops = append([]HopRec(nil), hops...)
	lastPane = pane
	lastTwin = twin
	lastGroups = append([]string(nil), groups...)
}

// LastHops returns the sealed hop records.
func LastHops() []HopRec { return append([]HopRec(nil), lastHops...) }

// LastPane returns the first seal digest.
func LastPane() string { return lastPane }

// LastTwin returns the second seal digest.
func LastTwin() string { return lastTwin }

// LastGroups returns sealed group keys.
func LastGroups() []string { return append([]string(nil), lastGroups...) }
