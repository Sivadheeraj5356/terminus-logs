package sim

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"

	"streamkit/internal/config"
	"streamkit/internal/model"
	"streamkit/internal/util"
)

func RunAll(work model.WorkloadFile, profile config.RuntimeProfile) (model.RecoveryReport, error) {
	results := make([]model.ScenarioResult, 0, len(work.Scenarios))
	for _, sc := range work.Scenarios {
		stats, sess := RunScenario(sc, profile, work.TickBudget)
		results = append(results, BuildResult(sc, stats, sess))
	}
	report := model.RecoveryReport{Scenarios: results}
	report.RecoveryDigest = RecoveryDigest(results)
	return report, nil
}

func RecoveryDigest(rows []model.ScenarioResult) string {
	ordered := append([]model.ScenarioResult(nil), rows...)
	sort.Slice(ordered, func(i, j int) bool {
		return ordered[i].ScenarioID < ordered[j].ScenarioID
	})
	var b strings.Builder
	for _, row := range ordered {
		fmt.Fprintf(&b, "%s:%d:%d:%d:%.2f:%d:%d:%d",
			row.ScenarioID,
			row.RecordsProcessed,
			row.FinalResidualRecords,
			row.PeakTickResidual,
			row.CommitsPer1000Records,
			row.AssignmentSpread,
			row.IdleMemberCount,
			row.PlacementSignature,
		)
	}
	return util.DigestHex(b.String())
}

func WriteReport(path string, report model.RecoveryReport) error {
	data, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return os.WriteFile(path, data, 0o644)
}
