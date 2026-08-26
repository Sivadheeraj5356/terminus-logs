package ingest

import (
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"immunoflow/pkg/api"
)

type Bundle struct {
	Regions []api.Region
	Lots    []api.Lot
	Routes  []api.Route
	Clinics []api.Clinic
	Demand  []api.DemandRow
	Config  api.Config
}

func readJSON(path string, out any) error {
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(raw, out)
}

func LoadConfig(path string) (api.Config, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return api.Config{}, err
	}
	cfg := api.Config{ReserveDoses: 40, VialSize: 5}
	for _, line := range strings.Split(string(raw), "\n") {
		p := strings.Split(line, "=")
		if len(p) != 2 {
			continue
		}
		k := strings.TrimSpace(p[0])
		v := strings.Trim(strings.TrimSpace(p[1]), "\"")
		n, parseErr := strconv.Atoi(v)
		if parseErr != nil {
			continue
		}
		if k == "reserve_doses" {
			cfg.ReserveDoses = n
		}
		if k == "vial_size" {
			cfg.VialSize = n
		}
	}
	return cfg, nil
}

func LoadAll(lab, cfg string) (Bundle, error) {
	var b Bundle
	if err := readJSON(filepath.Join(lab, "regions.json"), &b.Regions); err != nil {
		return b, err
	}
	if err := readJSON(filepath.Join(lab, "lots.json"), &b.Lots); err != nil {
		return b, err
	}
	if err := readJSON(filepath.Join(lab, "routes.json"), &b.Routes); err != nil {
		return b, err
	}
	if err := readJSON(filepath.Join(lab, "clinics.json"), &b.Clinics); err != nil {
		return b, err
	}
	if err := readJSON(filepath.Join(lab, "demand.json"), &b.Demand); err != nil {
		return b, err
	}
	c, err := LoadConfig(cfg)
	if err != nil {
		return b, err
	}
	b.Config = c
	return b, nil
}
