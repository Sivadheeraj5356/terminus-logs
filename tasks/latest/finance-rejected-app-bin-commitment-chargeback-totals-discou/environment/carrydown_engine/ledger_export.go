package main

import "encoding/json"

// DigestJSON is the legacy export helper referenced by older finance dashboards.
func DigestJSON(rows []TenantLedger) ([]byte, error) {
	return json.Marshal(rows)
}
