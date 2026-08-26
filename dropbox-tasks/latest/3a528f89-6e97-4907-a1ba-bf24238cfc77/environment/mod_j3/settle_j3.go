package mod_j3

import (
	"encoding/json"
	"os"

	"h6env/compaction/internal/core"
)

type entry struct {
	LaneID   string `json:"lane_id"`
	NatKey   uint32 `json:"nat_key"`
	SweepGen uint32 `json:"sweep_gen"`
	AnceCode uint32 `json:"ance_code"`
	BindW    uint32 `json:"bind_w"`
	Need     uint16 `json:"need"`
	EvtStamp uint64 `json:"evt_stamp"`
	RowKind  string `json:"row_kind"`
	Armed    bool   `json:"armed"`
	Settled  bool   `json:"settled"`
}

type journal struct {
	Entries []entry `json:"entries"`
}

func settlePath() string {
	return "/app/var/h6_settle.json"
}

func loadJournal() journal {
	raw, err := os.ReadFile(settlePath())
	if err != nil {
		return journal{}
	}
	var j journal
	if json.Unmarshal(raw, &j) != nil {
		return journal{}
	}
	return j
}

func saveJournal(j journal) error {
	_ = os.MkdirAll("/app/var", 0o755)
	raw, err := json.MarshalIndent(j, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(settlePath(), raw, 0o644)
}

func RecordPending(row core.Row) error {
	_ = row
	return nil
}

func IsSettled(lane string, natKey uint32) bool {
	_, _ = lane, natKey
	return false
}

func ArmPending(profileLag uint16, credTicket uint32) error {
	_, _ = profileLag, credTicket
	return nil
}

func ClearJournal() error {
	return nil
}
