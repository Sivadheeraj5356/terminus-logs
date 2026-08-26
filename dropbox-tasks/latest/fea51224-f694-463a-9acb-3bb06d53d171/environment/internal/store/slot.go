package store

type Span struct {
	Start int
	End   int
	Units int
}

type RunCtx struct {
	Pass     int
	Append   bool
	RowUnits int
}

type Batch struct {
	Offset    int
	Len       int
	SlotWidth int
	PeerTag   string
}

type PeerView struct {
	PeerTag       string
	SlotsFree     int
	ClearedUnits  int
	LaneTick      int
	PriorTick     int
	ArrayCleared  int
	VolSlotsFree  int
}

type Snapshot struct {
	FreeDelta int
	PriorTick int
	Pass      int
	Span      int
}

type Digest struct {
	Tick      int
	LaneTick  int
	BodyHex   string
	SlotsFree int
}

type Writer interface {
	Record(TraceLine) error
}

type TraceLine struct {
	Tick int `json:"tick"`
	AVal int `json:"a_val"`
	BVal int `json:"b_val"`
}

type ViewRow struct {
	PeerID       string `json:"peer_id"`
	BodyHex      string `json:"body_hex"`
	Epoch        int    `json:"epoch"`
	LaneTick     int    `json:"lane_tick"`
	SeriesNum    int    `json:"series_num"`
	SeriesDen    int    `json:"series_den"`
	SlotsFree    int    `json:"slots_free"`
	AppliedBytes int    `json:"applied_bytes"`
	SkippedBytes int    `json:"skipped_bytes"`
}

type SlotDigest struct {
	Views []ViewRow `json:"views"`
}

type TranscriptRow struct {
	PeerID      string `json:"peer_id"`
	SpanStart   int    `json:"span_start"`
	SpanEnd     int    `json:"span_end"`
	StrideUnits int    `json:"stride_units"`
	LaneTick    int    `json:"lane_tick"`
}

type TrimTranscript struct {
	Rows []TranscriptRow `json:"rows"`
}

type CycleWin struct {
	Cycle        int `json:"cycle"`
	AppliedBytes int `json:"applied_bytes"`
	SkippedBytes int `json:"skipped_bytes"`
}

type ConvergenceReport struct {
	Cycles []CycleWin `json:"cycles"`
}

type EmitStats struct {
	Forwarded int
	Skipped   int
}

type SlotSnap struct {
	Rows []SlotRow `json:"rows"`
}

type SlotRow struct {
	PeerTag      string `json:"peer_tag"`
	SlotsFree    int    `json:"slots_free"`
	ClearedUnits int    `json:"cleared_units"`
	LaneTick     int    `json:"lane_tick"`
	Tick         int    `json:"tick"`
}

type TrimEvt struct {
	Spans         []Span `json:"spans"`
	Tick          int    `json:"tick"`
	ClearedUnits  int    `json:"cleared_units"`
}

type UtilRatio struct {
	SeriesNum int `json:"series_num"`
	SeriesDen int `json:"series_den"`
}
