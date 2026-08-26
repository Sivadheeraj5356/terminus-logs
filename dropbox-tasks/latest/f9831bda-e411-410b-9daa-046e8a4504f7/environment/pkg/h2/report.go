package h2

import (
	"encoding/json"
	"os"
)

type Row struct {
	Role       string `json:"role"`
	ScoreHex string `json:"score_hex"`
	CoverHex    string `json:"cover_hex"`
	NcSkew   int    `json:"nc_skew"`
	LagCode  int    `json:"lag_code"`
	SlotID     string `json:"slot_id"`
}

type CycleResult struct {
	ProfileID   string `json:"profile_id"`
	PassMode     string `json:"pass_mode"`
	BandHex    string `json:"band_hex"`
	CarrySpan  int    `json:"carry_span"`
	BudgetUsed int    `json:"budget_used"`
	Rows       []Row  `json:"rows"`
}

type Summary struct {
	RowsTotal         int    `json:"rows_total"`
	MatrixStatus   string `json:"matrix_status"`
	CarrySpan         int    `json:"carry_span"`
	WitnessDigest     string `json:"witness_digest"`
}

type Witness struct {
	Cycles  []CycleResult `json:"cycles"`
	Summary Summary       `json:"summary"`
}

func frameBytes(root, name string) ([]byte, error) {
	return os.ReadFile(root + "/fixtures/b5/" + name + ".bin")
}

func frameUnit(ten *Profile) int {
	if ten.FrameUnit > 0 {
		return ten.FrameUnit
	}
	return 64
}

func grantUnit(ten *Profile) int {
	if ten.GrantUnit > 0 {
		return ten.GrantUnit
	}
	return 32
}

func ListModes() []string {
	return []string{"fresh_score", "rotate_split", "trim_holdout", "mirror_restore"}
}

func modeBudget(ten *Profile, mode string) int {
	_ = mode
	return ten.CarryBudget
}

func modeStamp(stamp, mode string) string {
	if mode == "fresh_score" {
		return stamp
	}
	return stamp + ":" + mode
}

func BuildCycle(root string, ten *Profile, mode string, cache map[string]int) (*CycleResult, error) {
	lines, err := LoadLedger(root)
	if err != nil {
		return nil, err
	}
	stamps := make(map[string]string)
	rows := make([]Row, 0, len(ten.Modules))
	cacheBefore := len(cache)
	for _, mod := range ten.Modules {
		line, ok := LookupLedger(lines, mod.Path, mod.Version)
		if !ok {
			line = LedgerLine{Path: mod.Path, Version: mod.Version, ThisUp: "v0"}
		}
		shard, err := LoadShard(root, mod.ShardRef)
		if err != nil {
			return nil, err
		}
		thisUp := PickLine(line.ThisUp, shard.ThisUp, line.Tomb || mod.Tomb)
		slot := SealSlot(mod.Path, mod.Version, ten.EpochDN, modeStamp(ten.EpochStamp, mode))
		if _, seen := cache[slot]; !seen {
			cache[slot] = len(cache) + 1
		}
		blob, err := frameBytes(root, mod.Frame)
		if err != nil {
			return nil, err
		}
		cover := FoldCover(ten.ProfilePfx, blob)
		st := ScoreHex(shard.Issuer, thisUp, shard.Serials)
		stamps[mod.Role] = st
		skew := 0
		code := 0
		if mod.EchoRole != "" {
			if echo, ok := stamps[mod.EchoRole]; ok {
				skew = NcSkew(st, echo)
				code = LagCode(st, echo)
			}
		}
		rows = append(rows, Row{
			Role: mod.Role, ScoreHex: st, CoverHex: cover,
			NcSkew: skew, LagCode: code, SlotID: slot,
		})
	}
	var stampList []string
	for _, r := range rows {
		stampList = append(stampList, r.ScoreHex)
	}
	fu := frameUnit(ten)
	gu := grantUnit(ten)
	newSlots := len(cache) - cacheBefore
	used := newSlots*fu + len(rows)*gu
	span := modeBudget(ten, mode) - used
	return &CycleResult{
		ProfileID: ten.ProfileID, PassMode: mode, BandHex: BandHex(stampList),
		CarrySpan: span, BudgetUsed: used, Rows: rows,
	}, nil
}

func BuildWitness(root string) (*Witness, error) {
	cache := map[string]int{}
	var cycles []CycleResult
	rowTotal := 0
	for _, tenant := range ListProfiles(root) {
		ten, err := LoadProfile(root, tenant)
		if err != nil {
			return nil, err
		}
		for _, mode := range ListModes() {
			cr, err := BuildCycle(root, ten, mode, cache)
			if err != nil {
				return nil, err
			}
			cycles = append(cycles, *cr)
			rowTotal += len(cr.Rows)
		}
	}
	sumSpan := 0
	status := "settled"
	for _, cycle := range cycles {
		if cycle.CarrySpan != 0 {
			sumSpan = cycle.CarrySpan
			status = "unsettled"
		}
		for _, row := range cycle.Rows {
			if row.NcSkew != 0 {
				status = "unsettled"
			}
		}
	}
	digest := WitnessDigest(cycles)
	return &Witness{
		Cycles: cycles,
		Summary: Summary{
			RowsTotal: rowTotal, MatrixStatus: status,
			CarrySpan: sumSpan, WitnessDigest: digest,
		},
	}, nil
}

func WriteWitness(path string, wit *Witness) error {
	raw, err := json.MarshalIndent(wit, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0644)
}
