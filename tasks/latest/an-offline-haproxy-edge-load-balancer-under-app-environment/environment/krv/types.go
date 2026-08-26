package krv

// Entry is one recorded cut journal entry.
type Entry struct {
	Arm     string `json:"arm"`
	Pending int    `json:"pending"`
	Hint    string `json:"hint"`
}
