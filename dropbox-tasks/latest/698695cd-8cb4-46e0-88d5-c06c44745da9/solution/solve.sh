#!/usr/bin/env bash
set -euo pipefail

cd /app
export PATH="/usr/local/go/bin:${PATH}"

python3 <<'PY'
from pathlib import Path

cat = Path("internal/config/catalog.go").read_text()
cat = cat.replace(
    """\t\tsort.Slice(m.Sessions[si].Frames, func(i, j int) bool {
\t\t\ta := m.Sessions[si].Frames[i]
\t\t\tb := m.Sessions[si].Frames[j]
\t\t\tif a.Path != b.Path {
\t\t\t\treturn a.Path < b.Path
\t\t\t}
\t\t\treturn a.FrameID < b.FrameID
\t\t})""",
    """\t\tsort.Slice(m.Sessions[si].Frames, func(i, j int) bool {
\t\t\ta := m.Sessions[si].Frames[i]
\t\t\tb := m.Sessions[si].Frames[j]
\t\t\tif a.TimestampS != b.TimestampS {
\t\t\t\treturn a.TimestampS < b.TimestampS
\t\t\t}
\t\t\treturn a.FrameID < b.FrameID
\t\t})""",
)
Path("internal/config/catalog.go").write_text(cat)

Path("internal/pngio/raster16.go").write_text('''package pngio

import (
	"image"
	"image/color"
	_ "image/png"
	"os"
)

type Frame struct {
	Width  int
	Height int
	Data   []uint16
}

func ReadGray16(path string) (*Frame, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	img, _, err := image.Decode(f)
	if err != nil {
		return nil, err
	}
	switch t := img.(type) {
	case *image.Gray16:
		b := t.Bounds()
		w, h := b.Dx(), b.Dy()
		data := make([]uint16, w*h)
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				data[y*w+x] = t.Gray16At(b.Min.X+x, b.Min.Y+y).Y
			}
		}
		return &Frame{Width: w, Height: h, Data: data}, nil
	default:
		b := img.Bounds()
		w, h := b.Dx(), b.Dy()
		data := make([]uint16, w*h)
		for y := 0; y < h; y++ {
			for x := 0; x < w; x++ {
				c := color.Gray16Model.Convert(img.At(b.Min.X+x, b.Min.Y+y)).(color.Gray16)
				data[y*w+x] = c.Y
			}
		}
		return &Frame{Width: w, Height: h, Data: data}, nil
	}
}
''')

Path("internal/mask/shrink.go").write_text('''package mask

func Erode(g *Grid, px int) *Grid {
	if px <= 0 {
		return g
	}
	cur := g
	for step := 0; step < px; step++ {
		nxt := &Grid{Width: cur.Width, Height: cur.Height, Data: make([]bool, len(cur.Data))}
		copy(nxt.Data, cur.Data)
		for y := 0; y < cur.Height; y++ {
			for x := 0; x < cur.Width; x++ {
				i := y*cur.Width + x
				if !cur.Data[i] {
					continue
				}
				for dy := -1; dy <= 1; dy++ {
					for dx := -1; dx <= 1; dx++ {
						ny, nx := y+dy, x+dx
						if ny < 0 || ny >= cur.Height || nx < 0 || nx >= cur.Width || !cur.Data[ny*cur.Width+nx] {
							nxt.Data[i] = false
							goto next
						}
					}
				}
			next:
			}
		}
		cur = nxt
	}
	return cur
}
''')

dark = Path("internal/radiometry/dark.go").read_text()
dark = dark.replace(
    "return c.DarkOffsetBase\n}",
    "return c.DarkOffsetBase + c.DarkOffsetRate*t\n}",
)
Path("internal/radiometry/dark.go").write_text(dark)

Path("internal/radiometry/normalize.go").write_text('''package radiometry

import "thermalcal/internal/terraform"

func CountsToTemperature(
	raw float64,
	t float64,
	perPixelDark, flatGain float64,
	c terraform.CameraConstants,
) float64 {
	doff := DarkOffset(t, c)
	linearized := (raw - doff - perPixelDark) / flatGain
	return c.Gain*linearized + c.Offset + c.EmissivityCorrection
}
''')

Path("internal/roi/roi.go").write_text('''package roi

import (
	"thermalcal/internal/mask"
	"thermalcal/internal/stats"
)

type Summary struct {
	UsablePixels   int
	TrimmedMeanC   float64
	RawMin         int
	RawMax         int
	MaskFraction   float64
	SaturatedCount int
}

func Summarize(
	raw []uint16,
	temps []float64,
	m *mask.Grid,
	noiseFloor int,
	saturation int,
	trimFraction float64,
) Summary {
	var values []float64
	rawMin := int(^uint(0) >> 1)
	rawMax := 0
	sat := 0
	total := len(raw)
	masked := 0
	for i, v := range raw {
		if !m.Data[i] {
			masked++
			continue
		}
		if int(v) >= saturation {
			sat++
			continue
		}
		if int(v) < noiseFloor {
			continue
		}
		if int(v) < rawMin {
			rawMin = int(v)
		}
		if int(v) > rawMax {
			rawMax = int(v)
		}
		values = append(values, temps[i])
	}
	if rawMin == int(^uint(0)>>1) {
		rawMin = 0
	}
	frac := 0.0
	if total > 0 {
		frac = float64(masked) / float64(total)
	}
	return Summary{
		UsablePixels:   len(values),
		TrimmedMeanC:   stats.TrimmedMean(values, trimFraction),
		RawMin:         rawMin,
		RawMax:         rawMax,
		MaskFraction:   frac,
		SaturatedCount: sat,
	}
}
''')

Path("internal/report/writer.go").write_text('''package report

import "os"

func EnsureNested(outputDir string) error {
	return os.MkdirAll(outputDir, 0o755)
}
''')

api = Path("internal/api/api.go").read_text()
api = api.replace(
    "summary := roi.Summarize(img.Data, tempsGrid, activeMask, manifest.NoiseFloorDN, manifest.SaturationDN)",
    "summary := roi.Summarize(img.Data, tempsGrid, activeMask, manifest.NoiseFloorDN, manifest.SaturationDN, manifest.TrimFraction)",
)
api = api.replace("fitRes := fit.FitCooling(times, temps)", """var fitRes fit.Result
\t\tif len(temps) > 0 {
\t\t\tfitRes = fit.WeightedLogLinear(times, temps, temps[len(temps)-1])
\t\t} else {
\t\t\tfitRes = fit.FitCooling(times, temps)
\t\t}""")
api = api.replace(
    "_ = report.EnsureNested(opts.OutputDir)\n\treturn writer.WriteAll(opts.OutputDir)",
    "if err := report.EnsureNested(opts.OutputDir); err != nil {\n\t\treturn err\n\t}\n\tif err := os.MkdirAll(filepath.Join(opts.OutputDir, \"intermediate\"), 0o755); err != nil {\n\t\treturn err\n\t}\n\treturn writer.WriteAll(opts.OutputDir)",
)
if "import (\n\t\"path/filepath\"" in api and "\"os\"" not in api:
    api = api.replace("import (\n\t\"path/filepath\"", "import (\n\t\"os\"\n\t\"path/filepath\"")
Path("internal/api/api.go").write_text(api)

print("patched oracle sources")
PY

go build -o /app/bin/thermalcal ./cmd/thermalcal
/app/bin/thermalcal /app/input_data /app/output_data
