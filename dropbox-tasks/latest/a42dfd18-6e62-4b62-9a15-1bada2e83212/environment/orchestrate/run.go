package orchestrate

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"

	"backuptrust/audit"
	"backuptrust/emit"
	"backuptrust/schema"
	"backuptrust/vault"

	"gopkg.in/yaml.v3"
)

const (
	rulesPath  = "/app/rules/escrow_matrix.yaml"
	reportPath = "/app/verdicts/backup_trust_report.json"
)

// Run loads archives, assesses each, and writes the trust report.
func Run() error {
	dir, err := vault.ResolveArchivesDir()
	if err != nil {
		return err
	}
	policy, err := loadPolicy(rulesPath)
	if err != nil {
		return err
	}

	var results []schema.ArchiveResult
	for i := 1; i <= 20; i++ {
		name := fmt.Sprintf("archive_%02d.json", i)
		path := filepath.Join(dir, name)
		archive, err := vault.LoadArchive(path)
		if err != nil {
			return fmt.Errorf("%s: %w", name, err)
		}
		results = append(results, audit.AssessArchive(archive, policy))
	}
	sort.Slice(results, func(i, j int) bool {
		return results[i].ArchiveID < results[j].ArchiveID
	})

	var atRisk, clean, critical, totalFindings, twSum int
	for _, r := range results {
		if r.RiskScore > 0 {
			atRisk++
		} else {
			clean++
		}
		if r.TrustTier == "critical" {
			critical++
		}
		totalFindings += len(r.Findings)
		twSum += r.Trustworthiness
	}
	mean := 0
	if len(results) > 0 {
		mean = twSum / len(results)
	}

	report := schema.Report{
		Summary: schema.Summary{
			ArchivesAnalyzed:    len(results),
			ArchivesAtRisk:      atRisk,
			CleanArchives:       clean,
			TotalFindings:       totalFindings,
			CriticalArchives:    critical,
			TrustworthinessMean: mean,
			ArchivesAbsPath:     dir,
		},
		Archives: results,
	}
	return emit.WriteReport(reportPath, report)
}

func loadPolicy(path string) (schema.Policy, error) {
	var p schema.Policy
	raw, err := os.ReadFile(path)
	if err != nil {
		return p, err
	}
	if err := yaml.Unmarshal(raw, &p); err != nil {
		return p, err
	}
	return p, nil
}
