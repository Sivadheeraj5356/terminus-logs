package pipe

import (
	"encoding/json"
	"os"
	"path/filepath"
	"sort"

	"pitctl/types"
	"pitctl/xfer"
)

func Materialize(foldID, outPath string) (types.PitReport, error) {
	fold, err := loadFold(foldID)
	if err != nil {
		return types.PitReport{}, err
	}
	events, err := loadEvents(fold.EventPack)
	if err != nil {
		return types.PitReport{}, err
	}
	pool, err := mergeFeatures(fold.FeaturePacks)
	if err != nil {
		return types.PitReport{}, err
	}
	remaps, err := loadRemaps(fold.RemapPack)
	if err != nil {
		return types.PitReport{}, err
	}

	gate := xfer.New()
	rows := []types.RowOut{}
	aud := []types.AuditEntry{}
	for _, ev := range events {
		resolved := resolveID(ev.EntityID, remaps, ev.EventMs)
		tEff := effTime(ev.EventMs, fold.WatermarkMs, fold.LagMs)
		picked, hit := gate.Recall(resolved, ev.EventMs)
		if !hit {
			picked = runPick(types.PickArgs{
				Entity: resolved, TMs: tEff, WmMs: fold.WatermarkMs, LagMs: fold.LagMs, Pool: pool,
			})
			gate.Remember(resolved, ev.EventMs, picked)
		}
		policy := "miss"
		if picked.Rev != nil {
			policy = "asof_wm"
		}
		row := makeRow(ev.EventID, resolved, ev.EventMs, picked.Rev)
		rows = append(rows, row)
		chosen := row.FeatRev
		aud = append(aud, makeAudit(ev.EventID, ev.EntityID, resolved, pool, ev.EventMs, picked.Candidates, chosen, policy))
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].EventID < rows[j].EventID })
	sort.Slice(aud, func(i, j int) bool { return aud[i].EventID < aud[j].EventID })
	report := types.PitReport{
		FoldID: foldID, RowCount: len(rows), Rows: rows, AuditTrace: aud,
		LedgerDigest: digestOf(foldID, rows),
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return report, err
	}
	b, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return report, err
	}
	if err := os.WriteFile(outPath, append(b, '\n'), 0o644); err != nil {
		return report, err
	}
	_ = saveJournal(foldID, report)
	return report, nil
}

func Status(foldID string) (map[string]any, error) {
	fold, err := loadFold(foldID)
	if err != nil {
		return nil, err
	}
	pool, err := mergeFeatures(fold.FeaturePacks)
	if err != nil {
		return nil, err
	}
	remaps, err := loadRemaps(fold.RemapPack)
	if err != nil {
		return nil, err
	}
	return map[string]any{
		"fold_id":      foldID,
		"rev_count":    len(pool),
		"alias_count":  len(remaps),
		"watermark_ms": fold.WatermarkMs,
		"lag_ms":       fold.LagMs,
	}, nil
}

func Verify(foldID, reportPath string) (map[string]any, error) {
	b, err := os.ReadFile(reportPath)
	if err != nil {
		return nil, err
	}
	var report types.PitReport
	if err := json.Unmarshal(b, &report); err != nil {
		return nil, err
	}
	entry, err := readJournal(foldID)
	if err != nil {
		return map[string]any{"ok": false, "reason": "missing_journal"}, nil
	}
	ok, reason := matchJournal(foldID, report, entry)
	return map[string]any{
		"ok":             ok,
		"reason":         reason,
		"journal_digest": entry.LedgerDigest,
		"report_digest":  report.LedgerDigest,
	}, nil
}
