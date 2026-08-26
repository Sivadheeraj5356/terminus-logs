package drive_h6

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"h6env/compaction/internal/core"
	"h6env/compaction/internal/scan_m4"
	"h6env/compaction/mod_b9"
	"h6env/compaction/mod_h4"
	"h6env/compaction/mod_q1"
	"h6env/compaction/mod_r2"
	"h6env/compaction/mod_s7"
)

type credSpec struct {
	Tag       string `toml:"tag"`
	LaneAWin  uint32 `toml:"lane_a_win"`
	LaneBWin  uint32 `toml:"lane_b_win"`
	Ticket    uint32 `toml:"ticket"`
	Warm      bool   `toml:"warm"`
	PhaseBase uint32 `toml:"phase_base"`
}

type bindCfg struct {
	LaneAWin uint32 `json:"lane_a_win"`
	LaneBWin uint32 `json:"lane_b_win"`
}

func envRoot() string {
	if v := os.Getenv("H6_ENV"); v != "" {
		return v
	}
	return "/app/environment"
}

func loadCred(tag string) (credSpec, error) {
	path := filepath.Join(envRoot(), "fixtures", fmt.Sprintf("cred_%s.toml", tag))
	raw, err := os.ReadFile(path)
	if err != nil {
		return credSpec{}, err
	}
	var c credSpec
	if _, err := parseSimpleTOML(string(raw), &c); err != nil {
		return credSpec{}, err
	}
	c.Tag = tag
	return c, nil
}

func parseSimpleTOML(raw string, c *credSpec) (int, error) {
	lines := splitLines(raw)
	for _, ln := range lines {
		ln = strings.TrimSpace(ln)
		if len(ln) == 0 || ln[0] == '#' {
			continue
		}
		parts := strings.SplitN(ln, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.TrimSpace(parts[1])
		if strings.HasPrefix(v, `"`) && strings.HasSuffix(v, `"`) {
			assignCred(k, strings.Trim(v, `"`), c)
			continue
		}
		if n, err := strconv.ParseUint(v, 10, 32); err == nil {
			assignCredNum(k, uint32(n), c)
		}
	}
	return len(raw), nil
}

func splitLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}

func assignCred(k, v string, c *credSpec) {
	switch k {
	case "tag":
		c.Tag = v
	}
}

func assignCredNum(k string, n uint32, c *credSpec) {
	switch k {
	case "lane_a_win":
		c.LaneAWin = n
	case "lane_b_win":
		c.LaneBWin = n
	case "ticket":
		c.Ticket = n
	case "phase_base":
		c.PhaseBase = n
	case "warm":
		if n != 0 {
			c.Warm = true
		}
	}
}

func loadBind() (bindCfg, error) {
	path := filepath.Join(envRoot(), "fixtures", "bind_cfg.toml")
	raw, err := os.ReadFile(path)
	if err != nil {
		return bindCfg{}, err
	}
	var b bindCfg
	_, _ = fmt.Sscanf(string(raw), "lane_a_win = %d\nlane_b_win = %d", &b.LaneAWin, &b.LaneBWin)
	return b, nil
}

func laneRows(lane string) ([]core.Row, error) {
	root := envRoot()
	tag := strings.ToLower(lane)
	seg, err := scan_m4.WalkLane(filepath.Join(root, "fixtures", fmt.Sprintf("seg_lane_%s_seed.jsonl", tag)), lane)
	if err != nil {
		return nil, err
	}
	book, err := scan_m4.WalkLane(filepath.Join(root, "fixtures", fmt.Sprintf("book_lane_%s_seed.jsonl", tag)), lane)
	if err != nil {
		return nil, err
	}
	return append(seg, book...), nil
}

func applyIngest(ticket uint32, rows []core.Row) ([]core.Row, error) {
	out := make([]core.Row, 0, len(rows))
	for i := range rows {
		b, err := mod_h4.Ingest_h4(ticket, &rows[i])
		if err != nil {
			return nil, err
		}
		if b.Commit {
			out = append(out, b.Row)
		}
	}
	return out, nil
}

func routeLag(rows []core.Row, lag uint16, credTicket uint32, spanExpect, laneASpan uint32) ([]core.Row, error) {
	out := make([]core.Row, 0, len(rows))
	for _, r := range rows {
		evt := core.Evt{
			LagTicket:  lag,
			CredTicket: credTicket,
			LaneID:     r.LaneID,
			NatKey:     r.NatKey,
			RowKind:    r.RowKind,
			SweepGen:   r.SweepGen,
			EvtStamp:   r.EvtStamp,
			AnceCode:   r.AnceCode,
			MarkerNeed: r.MarkerLag,
			SpanExpect: spanExpect,
			LaneASpan:  laneASpan,
		}
		rt, err := mod_b9.Lag_b9(lag, &evt)
		if err != nil {
			return nil, err
		}
		if rt.Ready {
			nr := r
			nr.MarkerLag = rt.Evt.LagTicket
			out = append(out, nr)
		}
	}
	return out, nil
}

func pickRows(gen uint32, live, stage []core.Row) ([]core.Row, error) {
	book := &core.Book{Rows: append([]core.Row{}, live...)}
	w, err := mod_s7.Pick_s7(gen, book, &core.Stage{Rows: stage})
	if err != nil {
		return nil, err
	}
	if len(book.Rows) != len(live) {
		return book.Rows, nil
	}
	if !w.Ok {
		return live, nil
	}
	return appendWin(live, w.Row), nil
}

func appendWin(rows []core.Row, win core.Row) []core.Row {
	for i, r := range rows {
		if r.LaneID == win.LaneID && r.NatKey == win.NatKey {
			rows[i] = win
			return rows
		}
	}
	return append(rows, win)
}

func spanHi(rows []core.Row, lane string) uint32 {
	var hi uint32
	for _, r := range rows {
		if r.LaneID == lane && r.NatKey > hi {
			hi = r.NatKey
		}
	}
	return hi
}

func phaseFor(c credSpec, lagSum uint32) uint32 {
	if c.Warm && c.Tag == "b" {
		return 3
	}
	return c.PhaseBase + (lagSum % 4)
}

func toObs(rows []core.Row, phase uint32, probe uint32, snap scan_m4.SnapSpec) []core.Obs {
	out := make([]core.Obs, 0, len(rows))
	for _, r := range rows {
		sh := spanHi(rows, r.LaneID)
		floor := scan_m4.SnapSpanFloor(snap, r.LaneID)
		if snap.GridRev >= 2 && floor > 0 {
			sh = floor
		} else if floor > 0 && sh < floor {
			sh = floor
		}
		out = append(out, core.Obs{
			LaneID:     r.LaneID,
			NatKey:     r.NatKey,
			BindW:      r.BindW,
			SweepGen:   r.SweepGen,
			PhaseCode:  phase,
			SpanHi:     sh,
			AnceCode:   r.AnceCode,
			WitFP:      r.WitFP,
			EvtStamp:   r.EvtStamp,
			RowKind:    r.RowKind,
			MarkerLag:  r.MarkerLag,
			ProbeScope: probe,
		})
	}
	return out
}

func ckptFrom(rows []core.Obs, lane string) core.Ckpt {
	var c core.Ckpt
	c.LaneID = lane
	hi := uint32(0)
	for _, r := range rows {
		if r.LaneID == lane && r.NatKey > hi {
			hi = r.NatKey
		}
	}
	for _, r := range rows {
		if r.LaneID == lane && r.NatKey == hi {
			c.SweepGen = r.SweepGen
			c.PhaseCode = r.PhaseCode
			c.SpanHi = r.SpanHi
			c.WitFP = r.WitFP
		}
	}
	return c
}

func snapPath() string {
	if os.Getenv("H6_RESET") == "1" {
		return filepath.Join(envRoot(), "fixtures", "snap_v2.dat")
	}
	return filepath.Join(envRoot(), "fixtures", "snap_v1.dat")
}

func RunCred(c credSpec, prior *core.OutDoc) (*core.OutDoc, error) {
	bind, _ := loadBind()
	grid, _ := scan_m4.LoadGrid(filepath.Join(envRoot(), "fixtures", "grid_v2.dat"))
	snap, _ := scan_m4.LoadSnap(snapPath())
	if c.LaneAWin == 0 {
		c.LaneAWin = grid.LaneAWin
		if c.LaneAWin == 0 {
			c.LaneAWin = bind.LaneAWin
		}
	}
	if c.LaneBWin == 0 {
		c.LaneBWin = grid.LaneBWin
		if c.LaneBWin == 0 {
			c.LaneBWin = bind.LaneBWin
		}
	}
	_ = snap
	aRows, err := laneRows("A")
	if err != nil {
		return nil, err
	}
	bRows, err := laneRows("B")
	if err != nil {
		return nil, err
	}
	aIn, err := applyIngest(c.Ticket, aRows)
	if err != nil {
		return nil, err
	}
	bIn, err := applyIngest(c.Ticket, bRows)
	if err != nil {
		return nil, err
	}
	lag := scan_m4.EpochLagFor(filepath.Join(envRoot(), "fixtures", "lag_epoch_profiles.json"), c.Ticket)
	if lag == 0 {
		lag = uint16(c.Ticket & 0xffff)
	}
	spanExpect := uint32(0)
	if prior != nil && c.Warm {
		for _, ck := range prior.Ckpts {
			if ck.LaneID == "A" {
				spanExpect = ck.SpanHi
			}
		}
	}
	aR, err := routeLag(aIn, lag, c.Ticket, spanExpect, spanHi(aIn, "A"))
	if err != nil {
		return nil, err
	}
	gen := c.Ticket + 1
	aPick, err := pickRows(gen, aR, nil)
	if err != nil {
		return nil, err
	}
	laneASpan := spanHi(aPick, "A")
	bR, err := routeLag(bIn, lag, c.Ticket, spanExpect, laneASpan)
	if err != nil {
		return nil, err
	}
	bPick, err := pickRows(gen, bR, nil)
	if err != nil {
		return nil, err
	}
	if prior != nil && c.Warm {
		for _, ck := range prior.Ckpts {
			if ck.LaneID == "A" && laneASpan != ck.SpanHi {
				return nil, fmt.Errorf("span gate blocked lane B warm emit")
			}
		}
	}
	var lagSum uint32
	for _, r := range append(aPick, bPick...) {
		lagSum += uint32(r.MarkerLag)
	}
	phase := phaseFor(c, lagSum)
	allPick := append(aPick, bPick...)
	probe := uint32(mod_q1.Range_q1(allPick))
	obs := append(toObs(aPick, phase, probe, snap), toObs(bPick, phase, probe, snap)...)
	doc := &core.OutDoc{}
	doc.Meta.RunTag = "h6"
	doc.Meta.CredTag = c.Tag
	doc.Meta.LaneAWin = c.LaneAWin
	doc.Meta.LaneBWin = c.LaneBWin
	doc.Rows = obs
	doc.Ckpts = []core.Ckpt{ckptFrom(obs, "A"), ckptFrom(obs, "B")}
	doc.PhaseWM = phase
	doc.SweepWM = gen
	if grid.Cells > 0 && doc.SweepWM > grid.Cells {
		doc.SweepWM = grid.Cells
	}
	_ = SaveCkpt(doc)
	if err := mod_r2.Read_r2(doc); err != nil {
		return nil, err
	}
	return doc, nil
}

func RunDual() error {
	cold, err := loadCred("a")
	if err != nil {
		return err
	}
	cold.Warm = false
	cold.PhaseBase = 1
	docA, err := RunCred(cold, nil)
	if err != nil {
		return err
	}
	warm, err := loadCred("b")
	if err != nil {
		return err
	}
	warm.Warm = true
	warm.PhaseBase = 2
	_, err = RunCred(warm, docA)
	return err
}

func RunWarmOnly() error {
	prior, err := LoadOut()
	if err != nil {
		return err
	}
	warm, err := loadCred("b")
	if err != nil {
		return err
	}
	warm.Warm = true
	warm.PhaseBase = 2
	_, err = RunCred(warm, prior)
	return err
}

func LoadOut() (*core.OutDoc, error) {
	raw, err := os.ReadFile("/app/output/out_h6.json")
	if err != nil {
		return nil, err
	}
	var d core.OutDoc
	if err := json.Unmarshal(raw, &d); err != nil {
		return nil, err
	}
	return &d, nil
}

func ResetState() {
	_ = os.Remove("/app/var/h6_ckpt.json")
}

func SaveCkpt(d *core.OutDoc) error {
	_ = os.MkdirAll("/app/var", 0o755)
	raw, err := json.MarshalIndent(d.Ckpts, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile("/app/var/h6_ckpt.json", raw, 0o644)
}
