package model

type Vault struct {
	MoveGen uint64   `json:"move_gen"`
	PtrRev  int      `json:"ptr_rev"`
	PtrPath string   `json:"ptr_path"`
	Seal    uint64   `json:"seal"`
	Mode    string   `json:"mode"`
	MapRows []MapRow `json:"map_rows"`
	Dirty   Dirty    `json:"dirty"`
	Tap     Tap      `json:"tap"`
	Slow    []Slot   `json:"slow_slots"`
	Fast    []Slot   `json:"fast_slots"`
	Foreign []Slot   `json:"foreign_slots"`
	RefPre  Ref      `json:"ref_pre"`
	RefPost Ref      `json:"ref_post"`
}

type Ref struct {
	Path      string `json:"path"`
	Rev       int    `json:"rev"`
	ActiveRow int    `json:"active_row"`
}

type Alias struct {
	Path string `json:"path"`
	Rev  int    `json:"rev"`
}

type MapRow struct {
	A   int   `json:"a"`
	B   int   `json:"b"`
	Off int64 `json:"off"`
}

type Dirty struct {
	Slots   []int  `json:"slots"`
	Barrier uint64 `json:"barrier"`
}

type Tap struct {
	Gen   uint64 `json:"gen"`
	Tally int    `json:"tally"`
}

type Slot struct {
	ID      int    `json:"id"`
	Payload string `json:"payload"`
	Epoch   uint64 `json:"epoch"`
	Bind    int    `json:"bind,omitempty"`
}

type Frame struct {
	Lagging bool
	Mode    string
	PrePath string
	PostPath string
	PostRev int
}

type TraceRow struct {
	Seq  int    `json:"seq"`
	Kind string `json:"kind"`
	Slot int    `json:"slot"`
	Note string `json:"note"`
	Rev  int    `json:"rev"`
}

type ClashRow struct {
	Field string `json:"field"`
	Was   string `json:"was"`
	Now   string `json:"now"`
	Rev   int    `json:"rev"`
}

type TapRow struct {
	Seq     int    `json:"seq"`
	Slot    int    `json:"slot"`
	Payload string `json:"payload"`
	Tally   int    `json:"tally"`
	Gen     uint64 `json:"gen"`
}

type HashView struct {
	Tag    string `json:"tag"`
	Rev    int    `json:"rev"`
	Fprint string `json:"fprint"`
	Move   uint64 `json:"move"`
}

type Record struct {
	Traces []TraceRow
	Clash  []ClashRow
	Hash   HashView
	Tap    []TapRow
	Gauge  string
}

type Event struct {
	Seq  int    `json:"seq"`
	Slot int    `json:"slot"`
	Gen  uint64 `json:"gen"`
}

type Live struct {
	Payload string
	Epoch   uint64
	Slot    int
}

type Candidate struct {
	Payload string
	Epoch   uint64
	Slot    int
}
