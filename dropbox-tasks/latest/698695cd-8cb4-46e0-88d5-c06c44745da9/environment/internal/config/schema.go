package config

type FrameRef struct {
	FrameID    string  `json:"frame_id"`
	TimestampS float64 `json:"timestamp_s"`
	Path       string  `json:"path"`
}

type SessionRef struct {
	SessionID string     `json:"session_id"`
	CameraID  string     `json:"camera_id"`
	Frames    []FrameRef `json:"frames"`
}

type CalRefs struct {
	Dark          string `json:"dark"`
	Flat          string `json:"flat"`
	ROIMask       string `json:"roi_mask"`
	DeadPixelMask string `json:"dead_pixel_mask"`
}

type Manifest struct {
	SchemaVersion int          `json:"schema_version"`
	NoiseFloorDN  int          `json:"noise_floor_dn"`
	SaturationDN  int          `json:"saturation_dn"`
	TrimFraction  float64      `json:"trim_fraction"`
	MaskErosionPx int          `json:"mask_erosion_px"`
	CalRefs       CalRefs      `json:"calrefs"`
	Sessions      []SessionRef `json:"sessions"`
}
