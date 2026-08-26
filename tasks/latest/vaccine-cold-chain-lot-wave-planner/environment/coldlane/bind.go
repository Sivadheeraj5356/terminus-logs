package coldlane

import (
	"encoding/json"
	"os"
	"os/exec"
	"path/filepath"

	"immunoflow/pkg/api"
)

type packReq struct {
	Assignments []api.LotAssignment `json:"assignments"`
}

type packResp struct {
	Pallets map[string][]string `json:"pallets"`
}

func grp_q(assign []api.LotAssignment) map[string][]string {
	out := map[string][]string{}
	for _, r := range assign {
		out[r.PalletID] = append(out[r.PalletID], r.LotID)
	}
	return out
}

func Bind(assign []api.LotAssignment) map[string][]string {
	dir, err := os.MkdirTemp("", "pkmerge-*")
	if err != nil {
		return grp_q(assign)
	}
	defer os.RemoveAll(dir)
	inPath := filepath.Join(dir, "in.json")
	outPath := filepath.Join(dir, "out.json")
	body, err := json.Marshal(packReq{Assignments: assign})
	if err != nil {
		return grp_q(assign)
	}
	if err := os.WriteFile(inPath, body, 0o644); err != nil {
		return grp_q(assign)
	}
	cmd := exec.Command("/app/bin/pkmerge", "--in", inPath, "--out", outPath)
	_ = cmd.Run()
	raw, err := os.ReadFile(outPath)
	if err != nil {
		return grp_q(assign)
	}
	var resp packResp
	_ = json.Unmarshal(raw, &resp)
	return grp_q(assign)
}
