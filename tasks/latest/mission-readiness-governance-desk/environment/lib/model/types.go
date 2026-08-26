package model

type Authority struct {
	Status      string `json:"status"`
	DecisionDoc string `json:"decision_doc"`
	Primary     string `json:"primary"`
}

type Evidence struct {
	ID       string `json:"id"`
	Axis     string `json:"axis"`
	Status   string `json:"status"`
	Weight   int    `json:"weight"`
	Source   string `json:"source"`
	Dissent  string `json:"dissent"`
	Resolved bool   `json:"resolved"`
	Note     string `json:"note"`
}

type Commitment struct {
	ID         string `json:"id"`
	Axis       string `json:"axis"`
	EvidenceID string `json:"evidence_id"`
	DueDay     int    `json:"due_day"`
	Closed     bool   `json:"closed"`
}

type Record struct {
	CaseID                 string       `json:"case_id"`
	MissionDays            int          `json:"mission_days"`
	TechnicalCertification string       `json:"technical_certification"`
	EmergencyAuthority     Authority    `json:"emergency_authority"`
	Evidence               []Evidence   `json:"evidence"`
	Commitments            []Commitment `json:"commitments"`
}

type Policy struct {
	AxisFloors              map[string]int `json:"axis_floors"`
	CriticalDissentStops    bool           `json:"critical_dissent_stops"`
	MajorDissentConditional bool           `json:"major_dissent_conditional"`
	CommitmentDueMarginDays int            `json:"commitment_due_margin_days"`
}

type CaseState struct {
	CaseID            string       `json:"case_id"`
	Runs              int          `json:"run_count"`
	OpenCommitments   []Commitment `json:"open_commitments"`
	ClosedCommitments []Commitment `json:"closed_commitments"`
	LastDecision      string       `json:"last_decision"`
}

type Assessment struct {
	CaseID                 string         `json:"case_id"`
	TechnicalCertification string         `json:"technical_certification"`
	EmergencyStatus        string         `json:"emergency_authority_status"`
	Decision               string         `json:"decision"`
	AxisScores             map[string]int `json:"axis_scores"`
	UnresolvedCritical     int            `json:"unresolved_critical_dissent"`
	UnresolvedMajor        int            `json:"unresolved_major_dissent"`
	OpenCommitmentIDs      []string       `json:"open_commitment_ids"`
	ClosedCommitmentIDs    []string       `json:"closed_commitment_ids"`
	ResilienceIndex        int            `json:"resilience_index"`
	ResilienceLabel        string         `json:"resilience_label"`
	StagnationPenalty      int            `json:"stagnation_penalty"`
	OverdueOpen            bool           `json:"overdue_open"`
	Evidence               []Evidence     `json:"evidence"`
	State                  CaseState      `json:"state"`
	AlternativesRejected   []string       `json:"alternatives_rejected"`
}

type JournalEntry struct {
	CaseID            string   `json:"case_id"`
	Decision          string   `json:"decision"`
	ResilienceIndex   int      `json:"resilience_index"`
	RunCount          int      `json:"run_count"`
	OpenCommitmentIDs []string `json:"open_commitment_ids"`
	StagnationPenalty int      `json:"stagnation_penalty"`
	OverdueOpen       bool     `json:"overdue_open"`
}
