package terraform

import (
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
)

type CameraConstants struct {
	Gain                 float64 `json:"gain"`
	Offset               float64 `json:"offset"`
	EmissivityCorrection float64 `json:"emissivity_correction"`
	DarkOffsetBase       float64 `json:"dark_offset_base"`
	DarkOffsetRate       float64 `json:"dark_offset_rate"`
}

type ManifestInfo struct {
	TerraformVersion string   `json:"terraform_version"`
	InstallPaths     []string `json:"install_paths"`
	ModulePath       string   `json:"module_path"`
}

func LoadManifest(root string) (*ManifestInfo, error) {
	p := filepath.Join(root, "vendor/hashicorp/terraform_manifest.json")
	data, err := os.ReadFile(p)
	if err != nil {
		return nil, err
	}
	var m ManifestInfo
	if err := json.Unmarshal(data, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

func ResolveBinary(root string) (string, error) {
	m, err := LoadManifest(root)
	if err != nil {
		return "", err
	}
	for _, p := range m.InstallPaths {
		if _, err := os.Stat(p); err == nil {
			return p, nil
		}
	}
	return "", fmt.Errorf("terraform binary not found")
}

func RenderConstants(projectRoot string) (map[string]CameraConstants, string, error) {
	bin, err := ResolveBinary(projectRoot)
	if err != nil {
		return nil, "", err
	}
	m, err := LoadManifest(projectRoot)
	if err != nil {
		return nil, "", err
	}
	module := m.ModulePath
	if module == "" {
		module = "/usr/local/share/calibration_tf"
	}
	cmd := exec.Command(bin, "-chdir="+module, "output", "-json", "calibration_constants")
	out, err := cmd.Output()
	if err != nil {
		return nil, "", fmt.Errorf("terraform output: %w", err)
	}
	var raw map[string]CameraConstants
	if err := json.Unmarshal(out, &raw); err != nil {
		return nil, "", err
	}
	version := m.TerraformVersion
	return raw, version, nil
}
