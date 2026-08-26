package kdescore

type Request struct {
	Signal   []float64 `json:"signal"`
	Sigma    float64   `json:"sigma"`
	Mode     *string   `json:"mode,omitempty"`
	Truncate *float64  `json:"truncate,omitempty"`
}

type Input struct {
	Inputs []Request `json:"inputs"`
}

type Result struct {
	Filtered []float64 `json:"filtered"`
}

type Output struct {
	Results []Result `json:"results"`
}
