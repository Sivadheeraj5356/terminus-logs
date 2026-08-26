package model

type IndexTable struct {
	Lanes     []Lane `json:"lanes"`
	CrossSeed int    `json:"cross_seed"`
	AadBase   []int  `json:"aad_base"`
}

type Lane struct {
	Grp uint32 `json:"grp"`
	Idx uint32 `json:"idx"`
	Ref string `json:"ref,omitempty"`
}

type CaseSpec struct {
	ID      string `json:"id"`
	Blob    string `json:"blob"`
	Sidecar string `json:"sidecar,omitempty"`
	PartOff int    `json:"part_off,omitempty"`
	Lanes   []Lane `json:"lanes,omitempty"`
	AadLane uint32 `json:"aad_lane,omitempty"`
	Epoch   uint32 `json:"epoch,omitempty"`
}

type CaseIndex struct {
	Entries []CaseSpec `json:"entries"`
}

type BindRow struct {
	Grp    uint32 `json:"grp"`
	KeyIdx uint32 `json:"key_idx"`
	AadHex string `json:"aad_hex"`
	RowHex string `json:"row_hex"`
}

type RunMeta struct {
	CaseID string `json:"case_id"`
	Phase  string `json:"phase"`
	Seq    int    `json:"seq"`
}

type SyncRecord struct {
	RunMeta        RunMeta   `json:"run_meta"`
	BindRows       []BindRow `json:"bind_rows"`
	PartSig        string    `json:"part_sig,omitempty"`
	CrossAadDigest string    `json:"cross_aad_digest"`
	RecordDigest   string    `json:"record_digest"`
}

type WorkState struct {
	Seq           int               `json:"seq"`
	LastKey       string            `json:"last_key"`
	Grp1AadPrefix string            `json:"grp1_aad_prefix"`
	Grp2AadPrefix string            `json:"grp2_aad_prefix"`
	AppendStamp   string            `json:"append_stamp"`
	FooterCache   map[string][]byte `json:"footer_cache,omitempty"`
}

type FooterView struct {
	Keys    [][]byte
	Groups  []GroupEntry
	Chunks  []ChunkEntry
	Raw     []byte
	Offset  int
	Version byte
}

type GroupEntry struct {
	GrpID   byte
	KeySlot byte
	AadSeed uint32
}

type ChunkEntry struct {
	GrpID  byte
	Offset uint32
	Length uint32
}

type Ctx struct {
	CaseID string
	Phase  string
	Seq    int
}
