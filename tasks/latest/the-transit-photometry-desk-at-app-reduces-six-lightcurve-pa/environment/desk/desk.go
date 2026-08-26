package desk

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"desk/kernel"
	"desk/phase"
	"desk/xvox"
)

type Row struct {
	Pack             string `json:"pack"`
	FreshDepth       int64  `json:"fresh_depth"`
	ResumedDepth     int64  `json:"resumed_depth"`
	SecondDepth      int64  `json:"second_depth"`
	ResidualFresh    int64  `json:"residual_fresh"`
	ResidualResumed  int64  `json:"residual_resumed"`
	DepthParityOk    bool   `json:"depth_parity_ok"`
	DualResumeOk     bool   `json:"dual_resume_ok"`
}

type Summary struct {
	AllParityOk bool `json:"all_parity_ok"`
	PackCount   int  `json:"pack_count"`
}

type Report struct {
	SchemaVersion int     `json:"schema_version"`
	Rows          []Row   `json:"rows"`
	Summary       Summary `json:"summary"`
}

type curveFile struct {
	Pack         string  `json:"pack"`
	Bins         int     `json:"bins"`
	ActiveStride int     `json:"active_stride"`
	HalfW        int     `json:"half_w"`
	WidthB       uint8   `json:"width_b"`
	Snapshot     uint32  `json:"snapshot"`
	Total        uint32  `json:"total"`
	Burst        bool    `json:"burst"`
	Samples      []int64 `json:"samples"`
}

func LoadSpec(path string) (phase.Spec, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return phase.Spec{}, err
	}
	var cf curveFile
	if err := json.Unmarshal(raw, &cf); err != nil {
		return phase.Spec{}, err
	}
	return phase.Spec{
		Name:         cf.Pack,
		Bins:         cf.Bins,
		ActiveStride: cf.ActiveStride,
		HalfW:        cf.HalfW,
		WidthB:       cf.WidthB,
		Snapshot:     cf.Snapshot,
		TotalSteps:   cf.Total,
		Burst:        cf.Burst,
		Samples:      cf.Samples,
	}, nil
}

func LoadOrder(indexPath string) ([]string, error) {
	raw, err := os.ReadFile(indexPath)
	if err != nil {
		return nil, err
	}
	var payload struct {
		Order []string `json:"order"`
	}
	if err := json.Unmarshal(raw, &payload); err != nil {
		return nil, err
	}
	return payload.Order, nil
}

func bundlePath(workDir, name string) string {
	return filepath.Join(workDir, name+".bundle")
}

func sampleAt(spec phase.Spec, step uint32) int64 {
	if len(spec.Samples) == 0 {
		return int64(step + 1)
	}
	return spec.Samples[int(step)%len(spec.Samples)]
}

func captureBlob(st *phase.State) *xvox.Blob {
	cells := append([]int64(nil), st.Cells...)
	return &xvox.Blob{
		Cursor:   st.Cursor,
		SavedStr: st.SavedStr,
		Phase:    st.Phase,
		Bins:     st.Bins,
		WidthB:   st.WidthB,
		Stride:   st.Stride,
		Cells:    cells,
	}
}

func applyBlob(st *phase.State, blob *xvox.Blob) {
	st.Cursor = blob.Cursor
	st.SavedStr = blob.SavedStr
	st.Phase = blob.Phase
	st.Bins = blob.Bins
	st.WidthB = blob.WidthB
	st.Stride = blob.Stride
	st.Cells = append([]int64(nil), blob.Cells...)
	st.ApronL = make([]int64, st.Stride)
	st.ApronR = make([]int64, st.Stride)
}

// FreshLane runs through the snapshot, publishes a bundle, remeshes, finishes.
func FreshLane(spec phase.Spec, workDir string) (depth int64, residual int64) {
	st := phase.NewState(spec)
	kernel.PrepareApron(st, spec)
	for st.Cursor < spec.Snapshot && st.Cursor < spec.TotalSteps {
		kernel.Advance(st, sampleAt(spec, st.Cursor))
	}
	blob := captureBlob(st)
	_ = xvox.Dump(bundlePath(workDir, spec.Name), blob, spec)

	kernel.Regrid(st, spec)
	kernel.PrepareApron(st, spec)
	for st.Cursor < spec.TotalSteps {
		kernel.Advance(st, sampleAt(spec, st.Cursor))
	}
	return kernel.DepthBits(st, spec, 0), kernel.ResidualScore(st)
}

// FreshDepthOnly computes the uninterrupted product without writing a bundle.
func FreshDepthOnly(spec phase.Spec) int64 {
	st := phase.NewState(spec)
	kernel.PrepareApron(st, spec)
	for st.Cursor < spec.Snapshot && st.Cursor < spec.TotalSteps {
		kernel.Advance(st, sampleAt(spec, st.Cursor))
	}
	kernel.Regrid(st, spec)
	kernel.PrepareApron(st, spec)
	for st.Cursor < spec.TotalSteps {
		kernel.Advance(st, sampleAt(spec, st.Cursor))
	}
	return kernel.DepthBits(st, spec, 0)
}

// ResumeLane restores from the published bundle and finishes the pack.
func ResumeLane(spec phase.Spec, workDir string) (depth int64, residual int64) {
	blob := &xvox.Blob{}
	if err := xvox.Load(bundlePath(workDir, spec.Name), blob, spec); err != nil {
		panic(err)
	}
	st := phase.NewState(spec)
	applyBlob(st, blob)
	st.ResumePass = 1
	if st.Stride != spec.ActiveStride && spec.ActiveStride > 0 {
		// stride may already match the live layout
	}
	kernel.PrepareApron(st, spec)
	for st.Cursor < spec.TotalSteps {
		kernel.Advance(st, sampleAt(spec, st.Cursor))
	}
	mark := uint8(0)
	if spec.Burst {
		mark = 1
	}
	return kernel.DepthBits(st, spec, mark), kernel.ResidualScore(st)
}

func EmitReport(outDir string, rows []Row, allOk bool) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	rep := Report{
		SchemaVersion: 1,
		Rows:          rows,
		Summary: Summary{
			AllParityOk: allOk,
			PackCount:   len(rows),
		},
	}
	raw, err := json.MarshalIndent(rep, "", "  ")
	if err != nil {
		return err
	}
	if err := os.WriteFile(filepath.Join(outDir, "depth_report.json"), raw, 0o644); err != nil {
		return err
	}
	parityFlag := 0
	if allOk {
		parityFlag = 1
	}
	var tr strings.Builder
	tr.WriteString(fmt.Sprintf("MATRIX schema=1 packs=%d parity=%d\n", len(rows), parityFlag))
	for _, r := range rows {
		pf, df := 0, 0
		if r.DepthParityOk {
			pf = 1
		}
		if r.DualResumeOk {
			df = 1
		}
		tr.WriteString(fmt.Sprintf(
			"PACK %s fresh=%d resumed=%d second=%d parity=%d dual=%d\n",
			r.Pack, r.FreshDepth, r.ResumedDepth, r.SecondDepth, pf, df,
		))
	}
	return os.WriteFile(filepath.Join(outDir, "matrix.transcript"), []byte(tr.String()), 0o644)
}
