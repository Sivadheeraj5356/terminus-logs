package profile

import (
	"encoding/json"
	"os"
)

type Profile struct {
	GreenhouseID              string   `json:"greenhouse_id"`
	TargetECmS                  float64  `json:"target_ec_mS"`
	PhMin                       float64  `json:"ph_min"`
	PhMax                       float64  `json:"ph_max"`
	MaxBatchVolumeMl            int      `json:"max_batch_volume_ml"`
	MaxDailyVolumeMlPerZone     int      `json:"max_daily_volume_ml_per_zone"`
	MinDoseCount                int      `json:"min_dose_count"`
	MaxECDriftIntegral          float64  `json:"max_ec_drift_integral"`
	GreenhouseTimezone          string   `json:"greenhouse_timezone"`
	ZoneIDs                     []string `json:"zone_ids"`
}

func Load(path string) (*Profile, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p Profile
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, err
	}
	return &p, nil
}

func (p *Profile) ZoneAllowed(zoneID string) bool {
	for _, z := range p.ZoneIDs {
		if z == zoneID {
			return true
		}
	}
	return false
}
