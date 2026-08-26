package inheritance_engine

type Event struct {
	Seq                      int      `json:"seq"`
	EventID                  string   `json:"event_id"`
	CoordinatorID            string   `json:"coordinator_id"`
	Kind                     string   `json:"kind"`
	PrivilegeTier            string   `json:"privilege_tier"`
	BusinessUnit             string   `json:"business_unit"`
	GrantorCoordinator       string   `json:"grantor_coordinator"`
	GranteeCoordinator       string   `json:"grantee_coordinator"`
	EntitlementKey           string   `json:"entitlement_key"`
	RequestorID              string   `json:"requestor_id"`
	EvalTargetID             string   `json:"eval_target_id"`
	Action                   string   `json:"action"`
	HasGovernanceAttestation bool     `json:"has_governance_attestation"`
	PropagatedEntitlements   []string `json:"propagated_entitlements"`
	ProvenanceRequestor      string   `json:"provenance_requestor"`
}

type DelegationSlice struct {
	DelegationSliceID                   string                 `json:"delegation_slice_id"`
	RequireAttestationOnOperational *bool                  `json:"require_attestation_on_operational"`
	BlockVendorToSovereign          *bool                  `json:"block_vendor_to_sovereign"`
	GovernanceOverrides             map[string]interface{} `json:"governance_overrides"`
	Events                          []Event                `json:"events"`
}

type InheritanceEdgeOut struct {
	GrantorCoordinator string `json:"grantor_coordinator"`
	GranteeCoordinator string `json:"grantee_coordinator"`
}

type CoordinatorOut struct {
	CoordinatorID        string   `json:"coordinator_id"`
	PrivilegeTier        string   `json:"privilege_tier"`
	EntitlementBindings  []string `json:"entitlement_bindings"`
	DelegationPoisonRisk string   `json:"delegation_poison_risk"`
}

type InheritanceJournalOut struct {
	FormatVersion   int `json:"format_version"`
	RecordsTotal    int `json:"records_total"`
	RecordsValid    int `json:"records_valid"`
	RecordsRejected int `json:"records_rejected"`
	DupSeqRejects   int `json:"dup_seq_rejects"`
	TruncatedTail   int `json:"truncated_tail"`
	PayloadBytes    int `json:"payload_bytes"`
}

type Finding struct {
	FindingID string `json:"finding_id"`
	EntityID  string `json:"entity_id"`
	Kind      string `json:"kind"`
	EventSeq  int    `json:"event_seq"`
	Action    string `json:"action"`
	Detail    string `json:"detail"`
}

type SliceOut struct {
	DelegationSliceID             string               `json:"delegation_slice_id"`
	Status                    string               `json:"status"`
	DuplicateEventsSkipped    int                  `json:"duplicate_events_skipped"`
	InheritanceJournal               InheritanceJournalOut       `json:"inheritance_journal"`
	InheritanceEdges          []InheritanceEdgeOut `json:"inheritance_edges"`
	Coordinators              []CoordinatorOut     `json:"coordinators"`
	Findings                  []Finding            `json:"findings"`
}

type Report struct {
	DelegationSlices []SliceOut `json:"delegation_slices"`
}

type coordinatorState struct {
	tier   string
	tenant string
	caps   map[string]struct{}
}
