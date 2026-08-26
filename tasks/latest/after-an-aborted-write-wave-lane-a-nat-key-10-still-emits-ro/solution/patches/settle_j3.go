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
	j := loadJournal()
	found := false
	for i := range j.Entries {
		if j.Entries[i].LaneID == row.LaneID && j.Entries[i].NatKey == row.NatKey {
			j.Entries[i].SweepGen = row.SweepGen
			j.Entries[i].AnceCode = row.AnceCode
			j.Entries[i].BindW = row.BindW
			j.Entries[i].Need = row.MarkerLag
			j.Entries[i].EvtStamp = row.EvtStamp
			j.Entries[i].RowKind = row.RowKind
			found = true
			break
		}
	}
	if !found {
		j.Entries = append(j.Entries, entry{
			LaneID:   row.LaneID,
			NatKey:   row.NatKey,
			SweepGen: row.SweepGen,
			AnceCode: row.AnceCode,
			BindW:    row.BindW,
			Need:     row.MarkerLag,
			EvtStamp: row.EvtStamp,
			RowKind:  row.RowKind,
		})
	}
	return saveJournal(j)
}

func IsSettled(lane string, natKey uint32) bool {
	j := loadJournal()
	for _, e := range j.Entries {
		if e.LaneID == lane && e.NatKey == natKey {
			return e.Settled
		}
	}
	return false
}

func ArmPending(profileLag uint16, credTicket uint32) error {
	j := loadJournal()
	for i := range j.Entries {
		if profileLag >= j.Entries[i].Need {
			j.Entries[i].Armed = true
		}
		if j.Entries[i].Armed && credTicket >= j.Entries[i].SweepGen {
			j.Entries[i].Settled = true
		}
	}
	return saveJournal(j)
}

func ClearJournal() error {
	_ = os.Remove(settlePath())
	return nil
}
