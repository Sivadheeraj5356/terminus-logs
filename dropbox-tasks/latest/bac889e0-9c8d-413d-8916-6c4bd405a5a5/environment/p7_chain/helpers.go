package p7_chain

import "balance_lab/p9_types"

func patchesInEra(era p9_types.EraSpan, rows []p9_types.ChronologyRow) []string {
	ordered := append([]p9_types.ChronologyRow(nil), rows...)
	for i := 0; i < len(ordered); i++ {
		for j := i + 1; j < len(ordered); j++ {
			if ordered[j].Seq < ordered[i].Seq {
				ordered[i], ordered[j] = ordered[j], ordered[i]
			}
		}
	}
	var patches []string
	inSpan := false
	for _, row := range ordered {
		if row.PatchID == era.StartPatch {
			inSpan = true
		}
		if inSpan {
			patches = append(patches, row.PatchID)
		}
		if row.PatchID == era.EndPatch {
			break
		}
	}
	return patches
}

func eraTotals(era p9_types.EraSpan, rows []p9_types.ChronologyRow, matches []p9_types.MatchRow) map[string]struct{ Picks, Wins int } {
	patchSet := map[string]bool{}
	for _, p := range patchesInEra(era, rows) {
		patchSet[p] = true
	}
	totals := map[string]struct{ Picks, Wins int }{}
	for _, row := range matches {
		if !patchSet[row.PatchID] {
			continue
		}
		cur := totals[row.Actor]
		cur.Picks += row.Picks
		cur.Wins += row.Wins
		totals[row.Actor] = cur
	}
	return totals
}

func seqByPatch(rows []p9_types.ChronologyRow) map[string]int {
	out := map[string]int{}
	for _, row := range rows {
		out[row.PatchID] = row.Seq
	}
	return out
}
