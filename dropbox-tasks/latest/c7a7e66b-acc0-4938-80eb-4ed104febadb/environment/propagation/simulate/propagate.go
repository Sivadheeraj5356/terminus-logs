package propagate

import (
	"sort"

	"svis/contracts"
)

func Simulate(cfg contracts.ProjectConfig) contracts.ProjectReport {
	pkgs := make([]contracts.PackageImpact, 0)
	for _, n := range cfg.Graph.Nodes {
		pkgs = append(pkgs, contracts.PackageImpact{
			PackageName: n.Name,
			BumpType:    "patch",
			BlastRadius: 1,
			RiskScore:   0.25,
			Tier:        "MEDIUM",
		})
	}
	sort.Slice(pkgs, func(i, j int) bool {
		return pkgs[i].PackageName < pkgs[j].PackageName
	})
	order := make([]string, 0)
	for _, p := range cfg.Graph.Proposed {
		order = append(order, p.Package)
	}
	return contracts.ProjectReport{
		ProjectID:            cfg.ProjectID,
		Status:               "SAFE",
		RiskScore:            0.25,
		UpgradeOrder:         order,
		PackagesImpacted:     pkgs,
		ConstraintViolations: []string{},
		PropagationPaths:     []string{},
		ScheduleConflicts:    []string{},
	}
}
