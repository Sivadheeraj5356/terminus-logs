package radiometry

import "thermalcal/internal/terraform"

func DarkOffset(t float64, c terraform.CameraConstants) float64 {
	return c.DarkOffsetBase
}

func PerPixelDark(ref []uint16) []float64 {
	out := make([]float64, len(ref))
	for i, v := range ref {
		out[i] = float64(v)
	}
	return out
}
