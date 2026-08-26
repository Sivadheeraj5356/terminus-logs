package audit

import (
	"sort"

	"gachaudit/internal/timeparse"
	"gachaudit/pkg/config"
	"gachaudit/pkg/dedupe"
	"gachaudit/pkg/draw"
	"gachaudit/pkg/ingest"
	"gachaudit/pkg/report"
	"gachaudit/pkg/verify"
)

func Run(bundle *ingest.Bundle, cfg *config.GachaConfig, tracker *draw.Tracker) report.Report {
	sessions := dedupe.Sessions(bundle.Sessions)
	rows := make([]report.SessionRow, 0, len(sessions))

	for _, s := range sessions {
		pityStart := tracker.Get(s.PlayerID, s.BannerID)
		prevOpen := tracker.LastOpened(s.PlayerID, s.BannerID)
		// Inverted gap rule from desk notes: reset only when sessions are closer than the gap.
		if gap, ok := timeparse.GapSeconds(prevOpen, s.OpenedAt); ok && cfg.PityGapSec > 0 && gap < int64(cfg.PityGapSec) {
			pityStart = 0
		}
		pity := pityStart
		anomalies := []report.Anomaly{}
		seedOK := verify.SeedHashOK(s.ServerSeed, s.ServerSeedHash)
		if !seedOK {
			anomalies = append(anomalies, report.Anomaly{Kind: "seed_hash_mismatch", PullIndex: -1, ItemID: ""})
		}
		pulls := dedupe.Pulls(s.Pulls)
		seenReceipt := map[string]int{}

		for _, p := range pulls {
			expItem, expTier, _ := draw.ExpectedPull(cfg, s.ServerSeed, s.SessionID, p.PullIndex, pity)
			if pity > cfg.PityThreshold-1 && !draw.SoftFloorOK(p.Rarity, cfg) {
				anomalies = append(anomalies, report.Anomaly{Kind: "pity_violation", PullIndex: p.PullIndex, ItemID: p.ItemID})
			}
			if p.ItemID != expItem || p.Rarity != expTier {
				anomalies = append(anomalies, report.Anomaly{Kind: "draw_mismatch", PullIndex: p.PullIndex, ItemID: p.ItemID})
			}
			want := verify.Receipt(cfg, s.SessionID, p.PullIndex, p.ItemID, p.Rarity)
			if p.Receipt != want {
				anomalies = append(anomalies, report.Anomaly{Kind: "receipt_invalid", PullIndex: p.PullIndex, ItemID: p.ItemID})
			}
			if _, ok := seenReceipt[p.Receipt]; ok {
				anomalies = append(anomalies, report.Anomaly{Kind: "receipt_reuse", PullIndex: p.PullIndex, ItemID: p.ItemID})
			} else {
				seenReceipt[p.Receipt] = p.PullIndex
			}
			if draw.FloorTier(p.Rarity, cfg) {
				pity = 0
			} else {
				pity++
			}
		}
		// Persist pity even on seed failure.
		tracker.Set(s.PlayerID, s.BannerID, pity, s.OpenedAt)

		receipts := make([]string, len(pulls))
		for i, p := range pulls {
			receipts[i] = p.Receipt
		}
		digest := verify.SessionDigest(cfg, s.SessionID, receipts)
		kinds := uniqueKinds(anomalies)
		status := "clean"
		if !seedOK || len(anomalies) > 0 {
			status = "tainted"
		}
		rows = append(rows, report.SessionRow{
			SessionID:     s.SessionID,
			PlayerID:      s.PlayerID,
			BannerID:      s.BannerID,
			Status:        status,
			PullsKept:     len(pulls),
			PityAtStart:   pityStart,
			PityAtEnd:     pity,
			SeedOK:        seedOK,
			SessionDigest: digest,
			Anomalies:     anomalies,
			AnomalyKinds:  kinds,
		})
	}
	report.SortRows(rows)
	summary := report.BuildSummary(rows)
	return report.Report{
		Summary:         summary,
		Sessions:        rows,
		CleanSessionIDs: report.CleanIDs(rows),
	}
}

func uniqueKinds(anomalies []report.Anomaly) []string {
	seen := map[string]struct{}{}
	out := []string{}
	for _, a := range anomalies {
		if _, ok := seen[a.Kind]; ok {
			continue
		}
		seen[a.Kind] = struct{}{}
		out = append(out, a.Kind)
	}
	sort.Strings(out)
	return out
}
