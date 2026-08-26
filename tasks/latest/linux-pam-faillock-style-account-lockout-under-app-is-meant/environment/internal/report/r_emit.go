package report

import (
	"encoding/json"

	"baylock/internal/app"
	"baylock/internal/domain"
	"baylock/internal/projection"
)

// WriteLedger is unfinished: digests and cross-view rows are incomplete.
func WriteLedger(path string) error {
	rt, err := app.LoadRuntime()
	if err != nil {
		return err
	}
	ledger := BuildLedger(rt, nil)
	data, err := json.MarshalIndent(ledger, "", "  ")
	if err != nil {
		return err
	}
	data = append(data, '\n')
	return app.WriteFile(path, data)
}

func BuildLedger(rt *domain.Runtime, snap *projection.Snapshot) domain.Ledger {
	if snap == nil {
		snap = &projection.Snapshot{GeneratedFrom: domain.GeneratedFrom}
	}
	return domain.Ledger{
		GeneratedFrom: domain.GeneratedFrom,
		AttemptCount:  rt.AttemptCount,
		Views:         []domain.ViewState{},
		Audits:        []domain.AuditRecord{},
	}
}
