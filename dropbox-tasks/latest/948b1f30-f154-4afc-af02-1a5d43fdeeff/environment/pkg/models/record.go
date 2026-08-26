package models

type SpectrumPoint struct {
	Wavenumber float64 `json:"wavenumber"`
	Intensity  float64 `json:"intensity"`
}

type RamanSpectrum struct {
	LaserWavenumber  float64        `json:"laser_wavenumber"`
	TemperatureRef   float64        `json:"temperature_reference"`
	AcquisitionTime  float64        `json:"acquisition_time"`
	Points           []SpectrumPoint `json:"points"`
}

type Peak struct {
	Center    float64 `json:"center"`
	Height    float64 `json:"height"`
	Width     float64 `json:"width"`
	Area      float64 `json:"area"`
}

type Report struct {
	Sample     ReportSample     `json:"sample"`
	Parameters ReportParameters `json:"parameters"`
	Summary    ReportSummary    `json:"summary"`
}

type ReportSample struct {
	SampleID   string `json:"sample_id"`
	Method     string `json:"method"`
}

type ReportParameters struct {
	LaserWavenumber     float64 `json:"laser_wavenumber"`
	RamanShiftCm        float64 `json:"raman_shift_cm"`
	BoseModel           string  `json:"bose_model"`
	FrequencyExponent   float64 `json:"frequency_exponent"`
	TemperatureOffset   float64 `json:"temperature_offset"`
}

type ReportSummary struct {
	StokesPeakCenter     float64 `json:"stokes_peak_center"`
	AntiStokesPeakCenter float64 `json:"anti_stokes_peak_center"`
	PeakShift            float64 `json:"peak_shift"`
	StokesIntensity      float64 `json:"stokes_intensity"`
	AntiStokesIntensity  float64 `json:"anti_stokes_intensity"`
	StokesAntiStokesRatio float64 `json:"stokes_anti_stokes_ratio"`
	TemperatureEstimate   float64 `json:"temperature_estimate"`
	Residual              float64 `json:"residual"`
}
