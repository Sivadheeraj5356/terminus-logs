package mod_h4

import (
	"encoding/json"
	"fmt"
	"os"
)

type hdrLine struct {
	Ver  int    `json:"ver"`
	Lane string `json:"lane"`
	Kind string `json:"kind"`
}

func ParseHdr(path string) (hdrLine, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return hdrLine{}, err
	}
	var h hdrLine
	if err := json.Unmarshal(raw, &h); err != nil {
		return hdrLine{}, err
	}
	if h.Ver < 1 {
		return hdrLine{}, fmt.Errorf("bad ver")
	}
	return h, nil
}
