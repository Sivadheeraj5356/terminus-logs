package accum

import (
	"sort"

	"orchard/canopyledger/config"
	"orchard/canopyledger/parse"
)

type Row struct {
	OrchardID   string  `json:"orchard_id,omitempty"`
	SensorID    string  `json:"sensor_id"`
	BucketEpoch int64   `json:"bucket_epoch"`
	CreditHours float64 `json:"credit_hours"`
	SampleCount int     `json:"sample_count"`
}

func Build(site config.Settings, readings []parse.Reading) []Row {
	base := config.EffectiveBase(site)
	unit := config.EffectiveIngestUnit(site)
	anchor := site.BucketAnchorEpoch

	sorted := append([]parse.Reading(nil), readings...)
	sort.Slice(sorted, func(i, j int) bool {
		if sorted[i].EpochSec != sorted[j].EpochSec {
			return sorted[i].EpochSec < sorted[j].EpochSec
		}
		return sorted[i].SensorID < sorted[j].SensorID
	})

	type key struct {
		sensor string
		bucket int64
	}
	acc := map[key]*Row{}
	prevEpoch := map[string]int64{}

	for _, r := range sorted {
		if r.Quality != "OK" {
			continue
		}
		wstart := WindowStart(r.EpochSec, anchor)
		k := key{sensor: r.SensorID, bucket: wstart}
		if acc[k] == nil {
			acc[k] = &Row{SensorID: r.SensorID, BucketEpoch: wstart}
		}
		prev := wstart
		if p, ok := prevEpoch[r.SensorID]; ok && p >= wstart {
			prev = p
		}
		intervalH := float64(r.EpochSec-prev) / 3600.0
		if intervalH < 0 {
			intervalH = 0
		}
		tempC := config.TempCelsius(unit, r.Temp)
		acc[k].CreditHours += IntervalCredit(tempC, base, intervalH)
		acc[k].SampleCount++
		prevEpoch[r.SensorID] = r.EpochSec
	}

	var out []Row
	for _, row := range acc {
		row.CreditHours = round4(row.CreditHours)
		out = append(out, *row)
	}
	return out
}

func round4(v float64) float64 {
	return float64(int(v*10000+0.5)) / 10000
}
