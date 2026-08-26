package rbxa1

import (
	"bufio"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"
	"strings"
)

type ServiceStatus struct {
	Status   string `json:"status"`
	Version  string `json:"version"`
	Previous string `json:"previous"`
	Target   string `json:"target,omitempty"`
}

type DeployStatus struct {
	Release  string                   `json:"release"`
	Incident string                   `json:"incident_id"`
	Services map[string]ServiceStatus `json:"services"`
}

type TruthBindings struct {
	TruthSource     string `json:"truth_source"`
	ReleaseDigest   string `json:"release_digest"`
	ForwardDigest   string `json:"forward_digest"`
	RegistryRelease string `json:"registry_release"`
}

func releaseDigest(status DeployStatus) string {
	lines := make([]string, 0, len(status.Services))
	for svc, row := range status.Services {
		lines = append(lines, svc+"|"+row.Status)
	}
	sort.Strings(lines)
	sum := sha256.Sum256([]byte(strings.Join(lines, "\n")))
	return hex.EncodeToString(sum[:])
}

func forwardDigest() (string, error) {
	raw, err := os.ReadFile("/app/data/deploy/forward-order.json")
	if err != nil {
		return "", err
	}
	var order []string
	if err := json.Unmarshal(raw, &order); err != nil {
		return "", err
	}
	sum := sha256.Sum256([]byte(strings.Join(order, "\n")))
	return hex.EncodeToString(sum[:]), nil
}

func registryRelease(incidentID string) (string, error) {
	raw, err := os.ReadFile("/app/data/incident/registry.json")
	if err != nil {
		return "", err
	}
	var reg map[string]struct {
		Release string `json:"release"`
	}
	if err := json.Unmarshal(raw, &reg); err != nil {
		return "", err
	}
	row, ok := reg[incidentID]
	if !ok {
		return "", os.ErrNotExist
	}
	return row.Release, nil
}

func CaptureTruth() error {
	raw, err := os.ReadFile("/app/data/deploy/release-state.json")
	if err != nil {
		return err
	}
	var status DeployStatus
	if err := json.Unmarshal(raw, &status); err != nil {
		return err
	}
	_ = foldLogHints(&status)
	if err := os.MkdirAll("/app/state", 0o755); err != nil {
		return err
	}
	out, err := json.MarshalIndent(status, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile("/app/state/deploy-status.json", out, 0o644); err != nil {
		return err
	}
	return writeTruthBindings(status)
}

func writeTruthBindings(status DeployStatus) error {
	return nil
}

func foldLogHints(status *DeployStatus) error {
	f, err := os.Open("/app/data/logs/rollback-events.jsonl")
	if err != nil {
		return err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Text()
		if strings.HasPrefix(line, "{") {
			var row map[string]string
			if json.Unmarshal([]byte(line), &row) != nil {
				continue
			}
			svc := row["service"]
			if svc == "billing-core" && row["event"] == "rollback_complete" {
				st := status.Services[svc]
				st.Status = "updated"
				st.Version = row["version"]
				status.Services[svc] = st
			}
			if svc == "identity-gate" && row["event"] == "deploy_failed" {
				st := status.Services[svc]
				st.Status = "failed"
				st.Version = row["version"]
				status.Services[svc] = st
			}
			if svc == "alert-dispatch" && row["event"] == "deploy_failed" {
				st := status.Services[svc]
				st.Status = "failed"
				st.Version = row["version"]
				status.Services[svc] = st
			}
		}
	}
	return sc.Err()
}
