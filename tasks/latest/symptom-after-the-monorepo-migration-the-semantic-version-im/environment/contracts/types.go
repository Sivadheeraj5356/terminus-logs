package contracts

type WorkspaceManifest struct {
	Projects []string `json:"projects"`
}

type GraphNode struct {
	Name    string `json:"name"`
	Version string `json:"version"`
}

type GraphEdge struct {
	Consumer   string `json:"consumer"`
	Provider   string `json:"provider"`
	Constraint string `json:"constraint"`
	Required   bool   `json:"required"`
	EdgeType   string `json:"edge_type,omitempty"`
}

type ProposedBump struct {
	Package     string `json:"package"`
	Target      string `json:"target"`
	ReleaseDate string `json:"release_date"`
}

type ReleaseGraph struct {
	Nodes    []GraphNode    `json:"nodes"`
	Edges    []GraphEdge    `json:"edges"`
	Proposed []ProposedBump `json:"proposed"`
}

type ProjectConfig struct {
	ProjectID      string             `json:"project_id"`
	FreezeDate     string             `json:"freeze_date"`
	RiskCutoff     *float64           `json:"risk_cutoff,omitempty"`
	BlastThreshold *int               `json:"blast_threshold,omitempty"`
	Weights        map[string]float64 `json:"weights,omitempty"`
	Graph          ReleaseGraph       `json:"graph"`
}

type PackageImpact struct {
	PackageName string  `json:"package_name"`
	BumpType    string  `json:"bump_type"`
	BlastRadius int     `json:"blast_radius"`
	RiskScore   float64 `json:"risk_score"`
	Tier        string  `json:"tier"`
}

type ProjectReport struct {
	ProjectID            string          `json:"project_id"`
	Status               string          `json:"status"`
	RiskScore            float64         `json:"risk_score"`
	UpgradeOrder         []string        `json:"upgrade_order"`
	PackagesImpacted     []PackageImpact `json:"packages_impacted"`
	ConstraintViolations []string        `json:"constraint_violations"`
	PropagationPaths     []string        `json:"propagation_paths"`
	ScheduleConflicts    []string        `json:"schedule_conflicts"`
}

type ImpactReport struct {
	Projects []ProjectReport `json:"projects"`
}
