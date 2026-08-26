package radiometry

import "thermalcal/internal/terraform"

func CountsToTemperature(
	raw float64,
	t float64,
	perPixelDark, flatGain float64,
	c terraform.CameraConstants,
) float64 {
	norm := raw / flatGain
	linearized := norm - perPixelDark
	return c.Gain*linearized + c.Offset
}
