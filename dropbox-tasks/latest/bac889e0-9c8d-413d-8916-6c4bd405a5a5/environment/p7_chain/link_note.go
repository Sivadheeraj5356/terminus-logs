package p7_chain

import (
	"strings"

	"balance_lab/p6_note"
	"balance_lab/p9_types"
)

func actorRationale(actor string, notes []p9_types.NoteRow, rows []p9_types.ChronologyRow) string {
	seq := seqByPatch(rows)
	bestSeq := -1
	bestDelta := 0
	found := false
	for _, note := range notes {
		if !strings.Contains(strings.ToLower(note.Headline), strings.ToLower(actor)) {
			continue
		}
		if seq[note.PatchID] > bestSeq {
			bestSeq = seq[note.PatchID]
			bestDelta = note.StatDelta
			found = true
		}
	}
	if !found {
		return p6_note.NoteTag("", 0)
	}
	return p6_note.NoteTag("", bestDelta)
}
