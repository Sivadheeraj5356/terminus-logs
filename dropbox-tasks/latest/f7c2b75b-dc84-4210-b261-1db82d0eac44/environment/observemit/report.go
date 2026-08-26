package observemit

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"os"
	"sort"

	"vivostep.local/sim/pkg/api"
)

type ReportInput struct {
	Cycles   []api.CycleRecord
	Surfaces []api.SurfaceMeasure
}

func CanonicalDigest(cycles []api.CycleRecord, surfaces []api.SurfaceMeasure) string {
	payload := struct {
		Cycles   []api.CycleRecord    `json:"cycles"`
		Surfaces []api.SurfaceMeasure `json:"surfaces"`
	}{
		Cycles:   canonicalCycles(cycles),
		Surfaces: canonicalSurfaces(surfaces),
	}
	b, _ := json.Marshal(payload)
	sum := sha256.Sum256(b)
	return hex.EncodeToString(sum[:])
}

func canonicalCycles(in []api.CycleRecord) []api.CycleRecord {
	out := make([]api.CycleRecord, len(in))
	copy(out, in)
	sort.Slice(out, func(i, j int) bool { return out[i].CycleID < out[j].CycleID })
	for i := range out {
		sort.Slice(out[i].GateTimings, func(a, b int) bool {
			return out[i].GateTimings[a].Phase < out[i].GateTimings[b].Phase
		})
	}
	return out
}

func canonicalSurfaces(in []api.SurfaceMeasure) []api.SurfaceMeasure {
	out := make([]api.SurfaceMeasure, len(in))
	copy(out, in)
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func WriteReport(path string, input ReportInput) error {
	digest := CanonicalDigest(input.Cycles, input.Surfaces)
	report := api.CycleReport{
		Cycles:       input.Cycles,
		Surfaces:     input.Surfaces,
		RecordDigest: digest,
	}
	b, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	b = append(b, '\n')
	return os.WriteFile(path, b, 0o644)
}
