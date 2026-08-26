package releasekit

type ComplianceReport struct {
	PolicyApplied        bool   `json:"policy_applied"`
	OpenAPIValid         bool   `json:"openapi_valid"`
	ReleasePinValid      bool   `json:"release_pin_valid"`
	DebugEndpointBlocked bool   `json:"debug_endpoint_blocked"`
	BuildPlanValid       bool   `json:"build_plan_valid"`
	ApprovedModuleCount  int    `json:"approved_module_count"`
	PolicyDigest         string `json:"policy_digest"`
}
