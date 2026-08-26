package ops

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"github.com/lab/cvstack/anchor"
	"github.com/lab/cvstack/filament"
	"github.com/lab/cvstack/harbor"
	"github.com/lab/cvstack/horizon"
	"github.com/lab/cvstack/internal/gauge"
	cvio "github.com/lab/cvstack/internal/io"
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/internal/vault"
	"github.com/lab/cvstack/lens"
	"github.com/lab/cvstack/meridian"
	"github.com/lab/cvstack/pulse"
	"github.com/lab/cvstack/ribbon"
	"github.com/lab/cvstack/splice"
	"github.com/lab/cvstack/tablet"
	"github.com/lab/cvstack/warp"
)

func relocationOpen(v model.Vault, alias model.Alias, active model.Ref) bool {
	if meridian.Open(v, alias) {
		return true
	}
	frame := horizon.Assemble(v, alias, active)
	if frame.Lagging {
		return true
	}
	if !harbor.QuorumClosed(v, alias, active) {
		return true
	}
	return v.Seal < v.MoveGen
}

func ClearOutputs(ws string) error {
	return cvio.ClearDir(filepath.Join(ws, "out"))
}

func WriteOutputs(ws string, rec model.Record) error {
	out := filepath.Join(ws, "out")
	if err := os.MkdirAll(out, 0o755); err != nil {
		return err
	}
	tf, err := os.Create(filepath.Join(out, "row_trace.jsonl"))
	if err != nil {
		return err
	}
	defer tf.Close()
	for _, row := range rec.Traces {
		b, _ := json.Marshal(row)
		if _, err := tf.Write(append(b, '\n')); err != nil {
			return err
		}
	}
	cf, err := os.Create(filepath.Join(out, "clash_rows.jsonl"))
	if err != nil {
		return err
	}
	defer cf.Close()
	for _, row := range rec.Clash {
		b, _ := json.Marshal(row)
		if _, err := cf.Write(append(b, '\n')); err != nil {
			return err
		}
	}
	if err := cvio.WriteJSON(filepath.Join(out, "hash_view.json"), rec.Hash); err != nil {
		return err
	}
	af, err := os.Create(filepath.Join(out, "tap_rows.jsonl"))
	if err != nil {
		return err
	}
	defer af.Close()
	for _, row := range rec.Tap {
		b, _ := json.Marshal(row)
		if _, err := af.Write(append(b, '\n')); err != nil {
			return err
		}
	}
	return cvio.WriteText(filepath.Join(out, "gauge.txt"), rec.Gauge)
}

func loadDest(ws string) ([]model.MapRow, error) {
	var rows []model.MapRow
	err := cvio.ReadJSON(filepath.Join(ws, "maps", "dest_bind.json"), &rows)
	return rows, err
}

func RunRecover(ws string) error {
	if err := ClearOutputs(ws); err != nil {
		return err
	}
	v, err := vault.Load(ws)
	if err != nil {
		return err
	}
	prePath := v.PtrPath
	if err := anchor.Seat(ws, &v); err != nil {
		return err
	}
	v, err = vault.Load(ws)
	if err != nil {
		return err
	}
	dst, err := loadDest(ws)
	if err != nil {
		return err
	}
	v.MapRows = splice.Knit(v.MapRows, dst)
	alias, _ := vault.LoadAlias(ws)
	active, _ := vault.LoadActive(ws)
	lagging := relocationOpen(v, alias, active)
	open := ribbon.OpenGate(v)
	syncErr := ribbon.SyncSlots(ws, v, open)
	tag := ribbon.Label(open, syncErr, lagging)
	pulse.CommitTap(&v, open, lagging)
	rec := tablet.Ink(ws, v, tag, prePath)
	rec.Gauge = gauge.Text(v) + fmt.Sprintf(" skew=%d", warp.Delta(v))
	if err := vault.Save(ws, v); err != nil {
		return err
	}
	if err := vault.SaveTap(ws, v.Tap); err != nil {
		return err
	}
	return WriteOutputs(ws, rec)
}

func RunInvariant(ws string) error {
	v, err := vault.Load(ws)
	if err != nil {
		return err
	}
	alias, _ := vault.LoadAlias(ws)
	active, _ := vault.LoadActive(ws)
	windowOpen := relocationOpen(v, alias, active)
	ok := v.PtrRev > 0 && len(v.MapRows) > 0
	msg := "fail"
	if ok {
		msg = "ok"
	}
	line := fmt.Sprintf(
		"probe %s rev=%d %s\n",
		msg,
		v.PtrRev,
		harbor.FormatProbe(v, windowOpen),
	)
	return cvio.WriteText(filepath.Join(ws, "out", "probe_view.txt"), line)
}

func RunStatus(ws string) error {
	v, err := vault.Load(ws)
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Join(ws, "out"), 0o755); err != nil {
		return err
	}
	foreign, _ := filament.ListForeign(ws)
	text := gauge.Text(v)
	if len(foreign) > 0 {
		text = fmt.Sprintf("%s foreign_n=%d", text, len(foreign))
	}
	return cvio.WriteText(filepath.Join(ws, "out", "gauge.txt"), text)
}

func RunRead(ws string, eventsPath string) error {
	if err := ClearOutputs(ws); err != nil {
		return err
	}
	v, err := vault.Load(ws)
	if err != nil {
		return err
	}
	if tap, err := vault.LoadTap(ws); err == nil {
		v.Tap = tap
	}
	alias, _ := vault.LoadAlias(ws)
	active, _ := vault.LoadActive(ws)
	events, err := loadEvents(eventsPath)
	if err != nil {
		return err
	}
	sort.Slice(events, func(i, j int) bool { return events[i].Seq < events[j].Seq })
	var rows []model.TapRow
	for _, ev := range events {
		g := ev.Gen
		if g == 0 {
			g = uint64(ev.Seq)
		}
		frame := horizon.Assemble(v, alias, active)
		lagging := relocationOpen(v, alias, active)
		frame.Lagging = lagging
		pulse.Tick(&v, g, lagging)
		payload := lens.Choose(ws, ev.Slot, v, frame)
		rows = append(rows, model.TapRow{
			Seq:     ev.Seq,
			Slot:    ev.Slot,
			Payload: payload,
			Tally:   v.Tap.Tally,
			Gen:     v.Tap.Gen,
		})
	}
	if err := writeTapOnly(ws, rows, gauge.Text(v)); err != nil {
		return err
	}
	return vault.SaveTap(ws, v.Tap)
}

func writeTapOnly(ws string, rows []model.TapRow, gaugeText string) error {
	out := filepath.Join(ws, "out")
	if err := os.MkdirAll(out, 0o755); err != nil {
		return err
	}
	af, err := os.Create(filepath.Join(out, "tap_rows.jsonl"))
	if err != nil {
		return err
	}
	defer af.Close()
	for _, row := range rows {
		b, _ := json.Marshal(row)
		if _, err := af.Write(append(b, '\n')); err != nil {
			return err
		}
	}
	return cvio.WriteText(filepath.Join(out, "gauge.txt"), gaugeText)
}

func loadEvents(eventsPath string) ([]model.Event, error) {
	var events []model.Event
	b, err := os.ReadFile(eventsPath)
	if err != nil {
		return nil, err
	}
	for _, line := range splitLines(string(b)) {
		if line == "" {
			continue
		}
		var ev model.Event
		if json.Unmarshal([]byte(line), &ev) == nil {
			events = append(events, ev)
		}
	}
	return events, nil
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

func FormatHelp() string {
	return `cvctl copy --sample <name> --dest <path>
cvctl status --workspace <path>
cvctl invariant --workspace <path>
cvctl recover --workspace <path>
cvctl read-replay --workspace <path> --events <path>`
}
