package runner

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"splicekit/internal/config"
	"splicekit/internal/epoch"
	"splicekit/internal/fixture"
	"splicekit/internal/lane"
	"splicekit/internal/ledger"
	"splicekit/internal/orchestrate"
	"splicekit/internal/surf"
	"splicekit/pkg/model"
)

func lastBundlePath() string {
	return filepath.Join(config.VarDir, "last_bundle.json")
}

func Reset() error {
	_ = os.Remove(config.ReportPath)
	_ = os.Remove(config.TracePath)
	_ = os.Remove(config.SettlePath)
	_ = os.Remove(lastBundlePath())
	_ = os.RemoveAll(config.OutDir)
	_ = os.MkdirAll(config.OutDir, 0o755)
	return ledger.Reset()
}

func Run(id string) (*model.Report, error) {
	sc, err := fixture.Load(id)
	if err != nil {
		return nil, err
	}
	if len(sc.Demands) == 0 {
		return nil, fmt.Errorf("empty demands")
	}

	pl, err := ledger.Load()
	if err != nil {
		return nil, err
	}

	bk := lane.NewBook()
	res, err := orchestrate.PlanR(config.OxkBin, sc, pl, bk)
	if err != nil {
		return nil, err
	}
	sealPeak, err := orchestrate.SealT(config.OxkBin, pl, sc, bk, res)
	if err != nil {
		return nil, err
	}
	if sealPeak > res.PeakMW {
		res.PeakMW = sealPeak
	}

	settleRows, score := orchestrate.Settle(sc, res.Served)
	gen, err := ledger.Generation()
	if err != nil {
		return nil, err
	}
	gen++
	prior, err := epoch.PriorHex(config.JournalPath)
	if err != nil {
		return nil, err
	}
	lines := digestLines(res.Served, res.Hops, sc)
	dig := surf.Seal(lines)
	rep := model.Report{
		ScenarioID:     sc.ScenarioID,
		Served:         res.Served,
		Rejected:       res.Rejected,
		TotalGbps:      sumGbps(sc, res.Served),
		PumpPeakMW:     res.PeakMW,
		SettleScore:    score,
		Feasible:       len(res.Rejected) == 0,
		Generation:     gen,
		PriorDigestHex: prior,
		DigestHex:      dig,
	}
	b := surf.Bundle{Report: rep, Hops: res.Hops, Settle: settleRows}
	if err := ledger.AppendJournal(fmt.Sprintf("%d|%s|%s", gen, sc.ScenarioID, dig)); err != nil {
		return nil, err
	}
	if err := os.MkdirAll(config.VarDir, 0o755); err != nil {
		return nil, err
	}
	raw, err := json.MarshalIndent(b, "", "  ")
	if err != nil {
		return nil, err
	}
	if err := os.WriteFile(lastBundlePath(), append(raw, '\n'), 0o644); err != nil {
		return nil, err
	}
	return &rep, nil
}

func sumGbps(sc *model.Scenario, served []string) int {
	set := map[string]bool{}
	for _, s := range served {
		set[s] = true
	}
	t := 0
	for _, d := range sc.Demands {
		if set[d.ID] {
			t += d.Gbps
		}
	}
	return t
}

func digestLines(served []string, hops []model.Hop, sc *model.Scenario) []string {
	by := map[string][]model.Hop{}
	for _, h := range hops {
		by[h.DemandID] = append(by[h.DemandID], h)
	}
	gbps := map[string]int{}
	for _, d := range sc.Demands {
		gbps[d.ID] = d.Gbps
	}
	var lines []string
	for _, id := range served {
		hs := by[id]
		sort.SliceStable(hs, func(i, j int) bool { return hs[i].Hop < hs[j].Hop })
		spans := make([]string, len(hs))
		lams := make([]string, len(hs))
		for i, h := range hs {
			spans[i] = h.SpanID
			lams[i] = strconv.Itoa(h.Lambda)
		}
		lines = append(lines, fmt.Sprintf(
			"D|%s|path=%s|lam=%s|gbps=%d",
			id, strings.Join(spans, ">"), strings.Join(lams, ","), gbps[id],
		))
	}
	return lines
}

func loadBundle() (*surf.Bundle, error) {
	raw, err := os.ReadFile(lastBundlePath())
	if err != nil {
		return nil, fmt.Errorf("no run")
	}
	var b surf.Bundle
	if err := json.Unmarshal(raw, &b); err != nil {
		return nil, err
	}
	return &b, nil
}

func Status() (string, error) {
	b, err := loadBundle()
	if err != nil {
		return "", err
	}
	return surf.StatusJSON(b.Report), nil
}

func Publish() error {
	b, err := loadBundle()
	if err != nil {
		return err
	}
	return surf.Write(*b)
}
