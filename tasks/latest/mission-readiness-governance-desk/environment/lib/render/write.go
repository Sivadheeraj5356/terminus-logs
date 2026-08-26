package render

import (
	"encoding/csv"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"

	"missiondesk/lib/intake"
	"missiondesk/lib/cstore"
	"missiondesk/lib/model"
)

func Publish(outDir string, assess model.Assessment, sf cstore.StateFile) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "determination.json"), assess); err != nil {
		return err
	}
	if err := writeCSV(filepath.Join(outDir, "evidence_matrix.csv"), assess); err != nil {
		return err
	}
	if err := writeMemo(filepath.Join(outDir, "board_memo.txt"), assess); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "board_state.json"), sf); err != nil {
		return err
	}
	return appendJournal(filepath.Join(outDir, "review_journal.jsonl"), assess)
}

func writeJSON(path string, v any) error {
	data, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(data, '\n'), 0o644)
}

func writeCSV(path string, assess model.Assessment) error {
	f, err := os.Create(path)
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	defer w.Flush()
	_ = w.Write([]string{"case_id", "row_id", "axis", "status", "source", "dissent", "resolved", "score", "decision", "resilience_index"})
	total := 0
	for _, item := range assess.Evidence {
		score := intake.Contribution(item)
		total += score
		_ = w.Write([]string{
			assess.CaseID, item.ID, item.Axis, item.Status, item.Source, item.Dissent,
			strconv.FormatBool(item.Resolved), strconv.Itoa(score), assess.Decision, strconv.Itoa(assess.ResilienceIndex),
		})
	}
	_ = w.Write([]string{assess.CaseID, "TOTAL", "all", "summary", "board", "none", "true", strconv.Itoa(total), assess.Decision, strconv.Itoa(assess.ResilienceIndex)})
	return w.Error()
}

func writeMemo(path string, assess model.Assessment) error {
	axes := make([]string, 0, len(assess.AxisScores))
	for k := range assess.AxisScores {
		axes = append(axes, k)
	}
	sort.Strings(axes)
	parts := []string{
		fmt.Sprintf("Case %s readiness determination: %s.", assess.CaseID, assess.Decision),
		fmt.Sprintf("Technical certification accepted as record: %s.", assess.TechnicalCertification),
		fmt.Sprintf("Emergency decision authority status: %s.", assess.EmergencyStatus),
		fmt.Sprintf("Axis scores: %s.", joinAxis(axes, assess.AxisScores)),
		fmt.Sprintf("Unresolved dissent: critical=%d major=%d.", assess.UnresolvedCritical, assess.UnresolvedMajor),
		fmt.Sprintf("Open commitments: %s.", strings.Join(assess.OpenCommitmentIDs, ",")),
		fmt.Sprintf("Closed commitments: %s.", strings.Join(assess.ClosedCommitmentIDs, ",")),
		fmt.Sprintf("Resilience index: %d (%s).", assess.ResilienceIndex, assess.ResilienceLabel),
		fmt.Sprintf("Stagnation penalty: %d.", assess.StagnationPenalty),
		fmt.Sprintf("Rejected alternatives: %s.", strings.Join(assess.AlternativesRejected, ",")),
	}
	return os.WriteFile(path, []byte(strings.Join(parts, "\n")+"\n"), 0o644)
}

func appendJournal(path string, assess model.Assessment) error {
	entry := model.JournalEntry{
		CaseID:            assess.CaseID,
		Decision:          assess.Decision,
		ResilienceIndex:   assess.ResilienceIndex,
		RunCount:          assess.State.Runs,
		OpenCommitmentIDs: assess.OpenCommitmentIDs,
		StagnationPenalty: assess.StagnationPenalty,
		OverdueOpen:       assess.OverdueOpen,
	}
	data, err := json.Marshal(entry)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(data, '\n'))
	return err
}

func joinAxis(keys []string, vals map[string]int) string {
	out := make([]string, 0, len(keys))
	for _, k := range keys {
		out = append(out, fmt.Sprintf("%s=%d", k, vals[k]))
	}
	return strings.Join(out, ",")
}
