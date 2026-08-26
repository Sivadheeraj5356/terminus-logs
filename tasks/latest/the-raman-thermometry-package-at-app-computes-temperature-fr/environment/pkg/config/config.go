package config

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

type Config struct {
	ReportPath         string
	SpectrumPath       string
	ConfidenceLevel    float64
	LaserWavenumber    float64
	RamanShiftCal      float64
	PeakWindowHalf     float64
	MinPeakHeight      float64
	BoseModel          string
	FrequencyExponent  float64
	TemperatureOffset  float64
	RatioConvention    string
}

func Load(configDir string) (*Config, error) {
	cfg := &Config{
		ReportPath:        "/app/output/report.json",
		SpectrumPath:      "/app/data/raman_spectrum.json",
		ConfidenceLevel:   0.95,
		LaserWavenumber:   15798.0,
		RamanShiftCal:     520.0,
		PeakWindowHalf:    15.0,
		MinPeakHeight:     10.0,
		BoseModel:         "approx",
		FrequencyExponent: 4.0,
		TemperatureOffset: 5.0,
		RatioConvention:   "stokes_over_anti",
	}
	if err := parseFile(configDir+"/default.toml", cfg); err != nil {
		return nil, err
	}
	if err := parseFile(configDir+"/calibration.toml", cfg); err != nil {
		return nil, err
	}
	return cfg, nil
}

func parseFile(path string, cfg *Config) error {
	f, err := os.Open(path)
	if err != nil {
		return err
	}
	defer f.Close()
	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if line == "" || strings.HasPrefix(line, "#") || !strings.Contains(line, "=") {
			continue
		}
		parts := strings.SplitN(line, "=", 2)
		key := strings.TrimSpace(parts[0])
		val := strings.Trim(strings.TrimSpace(parts[1]), `"`)
		switch key {
		case "report_path":
			cfg.ReportPath = val
		case "spectrum_path":
			cfg.SpectrumPath = val
		case "confidence_level":
			cfg.ConfidenceLevel, _ = strconv.ParseFloat(val, 64)
		case "laser_wavenumber":
			cfg.LaserWavenumber, _ = strconv.ParseFloat(val, 64)
		case "raman_shift_cal":
			cfg.RamanShiftCal, _ = strconv.ParseFloat(val, 64)
		case "peak_window_half":
			cfg.PeakWindowHalf, _ = strconv.ParseFloat(val, 64)
		case "min_peak_height":
			cfg.MinPeakHeight, _ = strconv.ParseFloat(val, 64)
		case "bose_model":
			cfg.BoseModel = val
		case "frequency_exponent":
			cfg.FrequencyExponent, _ = strconv.ParseFloat(val, 64)
		case "temperature_offset":
			cfg.TemperatureOffset, _ = strconv.ParseFloat(val, 64)
		case "ratio_convention":
			cfg.RatioConvention = val
		}
	}
	return scanner.Err()
}
