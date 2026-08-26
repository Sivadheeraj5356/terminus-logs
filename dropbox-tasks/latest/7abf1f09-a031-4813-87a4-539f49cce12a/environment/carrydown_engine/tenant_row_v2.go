package main

// TenantRowV2 holds an alternate tenant row layout used by older tooling.
type TenantRowV2 struct {
	TenantID string `json:"tenant_id"`
	Name     string `json:"name"`
	Region   string `json:"region"`
}
