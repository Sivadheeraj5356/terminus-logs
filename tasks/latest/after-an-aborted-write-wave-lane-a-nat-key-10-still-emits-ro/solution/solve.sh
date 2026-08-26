#!/bin/bash
set -euo pipefail

ENV="/app/environment"
cd "$ENV"

cat >internal/scan_m4/walk.go <<'PATCH_WALK_GO'
package scan_m4

import (
	"bufio"
	"encoding/json"
	"os"
	"strconv"
	"strings"

	"h6env/compaction/internal/core"
)

type seedLine struct {
	NatKey    uint32 `json:"nat_key"`
	RowKind   string `json:"row_kind"`
	SweepGen  uint32 `json:"sweep_gen"`
	AnceCode  uint32 `json:"ance_code"`
	EvtStamp  uint64 `json:"evt_stamp"`
	MarkerLag uint16 `json:"marker_lag"`
}

type GridSpec struct {
	LaneAWin uint32
	LaneBWin uint32
	Cells    uint32
}

type SnapSpec struct {
	LaneASpan uint32
	LaneBSpan uint32
	GridRev   uint32
}

type epochLine struct {
	Tag    string `json:"tag"`
	Lag    uint16 `json:"lag"`
	Ticket uint32 `json:"ticket"`
}

type epochFile struct {
	Epochs []epochLine `json:"epochs"`
}

func LoadGrid(path string) (GridSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return GridSpec{}, err
	}
	var g GridSpec
	for _, tok := range strings.Fields(string(raw)) {
		if strings.HasPrefix(tok, "lane_a=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "lane_a="), 10, 32)
			g.LaneAWin = uint32(v)
		}
		if strings.HasPrefix(tok, "lane_b=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "lane_b="), 10, 32)
			g.LaneBWin = uint32(v)
		}
		if strings.HasPrefix(tok, "cells=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(tok, "cells="), 10, 32)
			g.Cells = uint32(v)
		}
	}
	return g, nil
}

func LoadSnap(path string) (SnapSpec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return SnapSpec{}, err
	}
	var s SnapSpec
	for _, ln := range strings.Split(string(raw), "\n") {
		ln = strings.TrimSpace(ln)
		if strings.HasPrefix(ln, "lane_a_span=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "lane_a_span="), 10, 32)
			s.LaneASpan = uint32(v)
		}
		if strings.HasPrefix(ln, "lane_b_span=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "lane_b_span="), 10, 32)
			s.LaneBSpan = uint32(v)
		}
		if strings.HasPrefix(ln, "grid_rev=") {
			v, _ := strconv.ParseUint(strings.TrimPrefix(ln, "grid_rev="), 10, 32)
			s.GridRev = uint32(v)
		}
	}
	return s, nil
}

func GridBindW(g GridSpec, lane string) uint32 {
	if lane == "A" {
		return g.LaneAWin
	}
	return g.LaneBWin
}

func GridCeiling(g GridSpec) uint32 {
	return g.Cells
}

func SnapSpanFloor(s SnapSpec, lane string) uint32 {
	if lane == "A" {
		return s.LaneASpan
	}
	return s.LaneBSpan
}

func EpochLagFor(path string, ticket uint32) uint16 {
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	var ef epochFile
	if err := json.Unmarshal(raw, &ef); err != nil {
		return 0
	}
	var pick uint16
	for _, e := range ef.Epochs {
		if e.Ticket <= ticket && e.Lag > pick {
			pick = e.Lag
		}
	}
	return pick
}

func WalkLane(path, lane string) ([]core.Row, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []core.Row
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		var s seedLine
		if err := json.Unmarshal(sc.Bytes(), &s); err != nil {
			continue
		}
		out = append(out, core.Row{
			LaneID:    lane,
			NatKey:    s.NatKey,
			RowKind:   s.RowKind,
			SweepGen:  s.SweepGen,
			AnceCode:  s.AnceCode,
			EvtStamp:  s.EvtStamp,
			MarkerLag: s.MarkerLag,
		})
	}
	return out, sc.Err()
}
PATCH_WALK_GO

cat >mod_h4/ingest_h4.go <<'PATCH_INGEST_H4_GO'
package mod_h4

import (
	"fmt"
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
	"h6env/compaction/mod_j3"
)

func envRoot() string {
	return "/app/environment"
}

func ingest_h4(ticket uint32, row *core.Row) (core.Bound, error) {
	if row == nil {
		return core.Bound{}, fmt.Errorf("nil row")
	}
	out := *row
	out.Ticket = ticket
	grid, err := scan_m4.LoadGrid(filepath.Join(envRoot(), "fixtures", "grid_v2.dat"))
	if err != nil {
		return core.Bound{}, err
	}
	out.BindW = scan_m4.GridBindW(grid, out.LaneID)
	if out.RowKind == "void" {
		if ticket > 0 && ticket < out.SweepGen {
			_ = mod_j3.RecordPending(out)
			return core.Bound{Row: out, Commit: false}, nil
		}
		if !mod_j3.IsSettled(out.LaneID, out.NatKey) {
			_ = mod_j3.RecordPending(out)
			return core.Bound{Row: out, Commit: false}, nil
		}
	}
	out.WitFP = core.WitFPFor(out.LaneID, out.NatKey, out.SweepGen, out.AnceCode, out.BindW)
	return core.Bound{Row: out, Commit: true}, nil
}

func Ingest_h4(ticket uint32, row *core.Row) (core.Bound, error) {
	return ingest_h4(ticket, row)
}
PATCH_INGEST_H4_GO

cat >mod_s7/pick_s7.go <<'PATCH_PICK_S7_GO'
package mod_s7

import (
	"fmt"
	"path/filepath"
	"sort"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
)

func preferRow(a, b core.Row) bool {
	if a.SweepGen != b.SweepGen {
		return a.SweepGen > b.SweepGen
	}
	if a.RowKind == "void" && b.RowKind == "live" {
		return true
	}
	if a.RowKind == b.RowKind && a.EvtStamp > b.EvtStamp {
		return true
	}
	return false
}

func pick_s7(gen uint32, left *core.Book, right *core.Stage) (core.Win, error) {
	if left == nil {
		return core.Win{}, nil
	}
	grid, _ := scan_m4.LoadGrid(filepath.Join("/app/environment", "fixtures", "grid_v2.dat"))
	ceil := scan_m4.GridCeiling(grid)
	pool := append([]core.Row{}, left.Rows...)
	if right != nil {
		pool = append(pool, right.Rows...)
	}
	byKey := map[string]core.Row{}
	for _, r := range pool {
		key := fmt.Sprintf("%s:%d", r.LaneID, r.NatKey)
		if prev, ok := byKey[key]; !ok || preferRow(r, prev) {
			byKey[key] = r
		}
	}
	rows := buildRows(byKey, gen, ceil)
	left.Rows = rows
	if len(rows) == 0 {
		return core.Win{}, nil
	}
	return core.Win{Row: rows[0], Ok: true}, nil
}

func buildRows(byKey map[string]core.Row, gen uint32, ceil uint32) []core.Row {
	var keys []string
	for k := range byKey {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	rows := []core.Row{}
	for _, key := range keys {
		r := byKey[key]
		nr := r
		if nr.SweepGen < gen {
			nr.SweepGen = gen
		}
		if ceil > 0 && nr.SweepGen > ceil {
			nr.SweepGen = ceil
		}
		nr.WitFP = core.WitFPFor(nr.LaneID, nr.NatKey, nr.SweepGen, nr.AnceCode, nr.BindW)
		rows = append(rows, nr)
	}
	return rows
}

func Pick_s7(gen uint32, left *core.Book, right *core.Stage) (core.Win, error) {
	return pick_s7(gen, left, right)
}
PATCH_PICK_S7_GO

cat >mod_b9/lag_b9.go <<'PATCH_LAG_B9_GO'
package mod_b9

import (
	"fmt"
	"path/filepath"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
	"h6env/compaction/mod_j3"
)

func lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	if evt == nil {
		return core.Routed{}, nil
	}
	e := *evt
	e.LagTicket = lag
	profileLag := scan_m4.EpochLagFor(filepath.Join("/app/environment", "fixtures", "lag_epoch_profiles.json"), e.CredTicket)
	if profileLag > 0 {
		e.LagTicket = profileLag
	}
	_ = mod_j3.ArmPending(e.LagTicket, e.CredTicket)
	if evt.SpanExpect > 0 && evt.LaneID == "B" && evt.LaneASpan != evt.SpanExpect {
		return core.Routed{}, fmt.Errorf("span gate blocked warm lane B emit")
	}
	return core.Routed{Ready: true, Evt: e}, nil
}

func Lag_b9(lag uint16, evt *core.Evt) (core.Routed, error) {
	return lag_b9(lag, evt)
}
PATCH_LAG_B9_GO

cat >mod_r2/read_r2.go <<'PATCH_READ_R2_GO'
package mod_r2

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"

	"h6env/compaction/internal/core"
)

func preferObs(a, b core.Obs) bool {
	if a.SweepGen != b.SweepGen {
		return a.SweepGen > b.SweepGen
	}
	if a.RowKind == "void" && b.RowKind == "live" {
		return true
	}
	return a.EvtStamp >= b.EvtStamp
}

func read_r2(doc *core.OutDoc) error {
	if doc == nil {
		doc = &core.OutDoc{}
	}
	byKey := map[string]core.Obs{}
	for _, r := range doc.Rows {
		key := fmt.Sprintf("%s:%d", r.LaneID, r.NatKey)
		if prev, ok := byKey[key]; !ok || preferObs(r, prev) {
			byKey[key] = r
		}
	}
	rows := collectObs(byKey)
	doc.Rows = rows
	doc.RollFP = core.RollFP(rows)
	path := "/app/output/out_h6.json"
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, raw, 0o644)
}

func collectObs(byKey map[string]core.Obs) []core.Obs {
	var keys []string
	for k := range byKey {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	rows := []core.Obs{}
	for _, key := range keys {
		rows = append(rows, byKey[key])
	}
	return rows
}

func Read_r2(doc *core.OutDoc) error {
	return read_r2(doc)
}
PATCH_READ_R2_GO

cat >mod_q1/range_q1.go <<'PATCH_RANGE_Q1_GO'
package mod_q1

import (
	"h6env/compaction/internal/core"
)

func range_q1(rows []core.Row) uint64 {
	var acc uint64
	for _, r := range rows {
		if len(r.WitFP) > 0 {
			acc += uint64(r.WitFP[0])
		}
	}
	return acc % 1000000
}

func Range_q1(rows []core.Row) uint64 {
	return range_q1(rows)
}
PATCH_RANGE_Q1_GO

cat >mod_j3/settle_j3.go <<'PATCH_SETTLE_J3_GO'
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
PATCH_SETTLE_J3_GO

python3 - <<'PY'
from pathlib import Path

path = Path("/app/environment/internal/drive_h6/run.go")
text = path.read_text()
if "h6env/compaction/mod_j3" not in text:
    text = text.replace(
        '\t"h6env/compaction/mod_h4"\n',
        '\t"h6env/compaction/mod_h4"\n\t"h6env/compaction/mod_j3"\n',
        1,
    )
old = """func ResetState() {
\t_ = os.Remove(\"/app/var/h6_ckpt.json\")
}"""
new = """func ResetState() {
\t_ = os.Remove(\"/app/var/h6_ckpt.json\")
\t_ = mod_j3.ClearJournal()
}"""
if old not in text:
    raise SystemExit("ResetState block not found in drive_h6/run.go")
path.write_text(text.replace(old, new, 1))

PY

bash "$ENV/tooling/rebuild_h6.sh"
bash /app/tooling/run_h6.sh
