package led

// Entry is one committed ledger line in state/ledger.jsonl.
type Entry struct {
	Prev  string `json:"prev"`
	Gen   int    `json:"gen"`
	Floor int    `json:"floor"`
	Epoch int    `json:"epoch"`
	Arm   string `json:"arm"`
	Seal  string `json:"seal"`
	Tx    string `json:"tx"`
	Hash  string `json:"hash"`
}
