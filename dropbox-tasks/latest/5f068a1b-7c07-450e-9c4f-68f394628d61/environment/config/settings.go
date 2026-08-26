package config

import (
	"os"
	"strconv"
	"strings"
)

type Settings struct {
	OrchardID         string  `toml:"orchard_id"`
	BaseTempC         float64 `toml:"base_temp_c"`
	IngestUnit        string  `toml:"ingest_unit"`
	BucketAnchorEpoch int64   `toml:"bucket_anchor_epoch"`
}

func LoadSettings(path string) (Settings, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Settings{}, err
	}
	var site Settings
	if err := decodeToml(string(data), &site); err != nil {
		return Settings{}, err
	}
	if site.IngestUnit == "" {
		site.IngestUnit = "C"
	}
	return site, nil
}

func EffectiveBase(site Settings) float64 {
	if env := os.Getenv("ORCHARD_BASE_C"); env != "" {
		if v, err := strconv.ParseFloat(env, 64); err == nil {
			return v
		}
	}
	if site.BaseTempC != 0 {
		return site.BaseTempC
	}
	return 7.2
}

func EffectiveIngestUnit(site Settings) string {
	if env := os.Getenv("ORCHARD_INGEST_UNIT"); env != "" {
		return strings.ToUpper(env)
	}
	if site.IngestUnit != "" {
		return strings.ToUpper(site.IngestUnit)
	}
	return "C"
}

func TempCelsius(unit string, temp float64) float64 {
	if strings.ToUpper(unit) == "F" {
		return (temp - 32.0) * 5.0 / 9.0
	}
	return temp
}
