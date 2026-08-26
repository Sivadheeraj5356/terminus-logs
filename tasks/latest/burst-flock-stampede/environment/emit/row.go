package emit

// Row is one coordination trace matrix record.
type Row struct {
	Scenario          string `json:"scenario"`
	SliceEpoch        int    `json:"slice_epoch"`
	MarkerFPHost      string `json:"marker_fp_host"`
	MarkerFPPeer      string `json:"marker_fp_peer"`
	HoldGap           int64  `json:"hold_gap"`
	StagingLag        int64  `json:"staging_lag"`
	CheckpointEpoch   int    `json:"checkpoint_epoch"`
	LineageToken      string `json:"lineage_token"`
	PreservationStamp string `json:"preservation_stamp"`
	RowSeal           string `json:"row_seal"`
}

// Envelope is the top-level coordination trace document.
type Envelope struct {
	Runs         []Row  `json:"runs"`
	ReportDigest string `json:"report_digest"`
	ReplayToken  string `json:"replay_token"`
}
