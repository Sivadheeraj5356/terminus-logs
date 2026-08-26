package export

import (
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"ot7/internal/paths"
)

type ProfileResult struct {
	Label         string  `json:"label"`
	InstanceID    string  `json:"instance_id"`
	Accepted      bool    `json:"accepted"`
	Rows          int     `json:"rows"`
	Cols          int     `json:"cols"`
	PlanDigestHex string  `json:"plan_digest_hex"`
	Wasserstein   float64 `json:"wasserstein"`
}

type Report struct {
	Generation      int             `json:"generation"`
	PolicyEpoch     int             `json:"policy_epoch"`
	ReportDigestHex string          `json:"report_digest_hex"`
	Profiles        []ProfileResult `json:"profiles"`
}

func InstanceDigest(raw []byte) string {
	sum := sha256.Sum256(raw)
	return hex.EncodeToString(sum[:])
}

func PlanDigest(plan [][]float64) string {
	var parts []string
	for i := range plan {
		for j := range plan[i] {
			parts = append(parts, fmt.Sprintf("%d,%d:%.17e", i, j, plan[i][j]))
		}
	}
	sum := sha256.Sum256([]byte(strings.Join(parts, ";")))
	return hex.EncodeToString(sum[:])
}

func ReportDigest(gen, epoch int, digests []string) string {
	line := fmt.Sprintf("generation=%d|policy_epoch=%d|digests=%s", gen, epoch, strings.Join(digests, ","))
	sum := sha256.Sum256([]byte(line))
	return hex.EncodeToString(sum[:])
}

func WriteReport(rep Report) error {
	_ = os.MkdirAll(paths.Output, 0o777)
	b, _ := json.MarshalIndent(rep, "", "  ")
	return os.WriteFile(filepath.Join(paths.Output, "mass_report.json"), b, 0o644)
}

func WriteTrace(rows [][]string) error {
	_ = os.MkdirAll(paths.Output, 0o777)
	f, err := os.Create(filepath.Join(paths.Output, "plan_trace.csv"))
	if err != nil {
		return err
	}
	defer f.Close()
	w := csv.NewWriter(f)
	_ = w.Write([]string{"label", "i", "j", "p_ij", "c_ij"})
	for _, r := range rows {
		_ = w.Write(r)
	}
	w.Flush()
	return w.Error()
}

func LoadReport() (Report, error) {
	b, err := os.ReadFile(filepath.Join(paths.Output, "mass_report.json"))
	if err != nil {
		return Report{}, err
	}
	var r Report
	err = json.Unmarshal(b, &r)
	return r, err
}
