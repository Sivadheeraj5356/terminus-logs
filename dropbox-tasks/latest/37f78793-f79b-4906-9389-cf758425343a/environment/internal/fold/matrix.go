package fold

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
)

type RunRow map[string]any

type Matrix struct {
	MatrixTag      string   `json:"matrix_tag"`
	DepthLimit     int      `json:"depth_limit"`
	Runs           []RunRow `json:"runs"`
	ViolationTotal int      `json:"violation_total"`
	CrossDigest    string   `json:"cross_digest"`
	RepeatStamp    string   `json:"repeat_stamp"`
}

// FoldMatrix builds the graded witness.
func FoldMatrix(runs []RunRow) (Matrix, error) {
	violationTotal := 0
	for _, row := range runs {
		v, _ := asInt(row["violation_rows"])
		violationTotal += v
	}

	var cleanRuns []RunRow
	for _, row := range runs {
		clean := RunRow{}
		for k, v := range row {
			if k == "violations" {
				continue
			}
			clean[k] = v
		}
		cleanRuns = append(cleanRuns, clean)
	}

	stampPayload, err := json.Marshal(cleanRuns)
	if err != nil {
		return Matrix{}, err
	}
	sum := sha256.Sum256(stampPayload)
	stamp := hex.EncodeToString(sum[:])[:16]

	var crossParts string
	for _, row := range runs {
		dig, _ := row["digest_hex"].(string)
		crossParts += dig
	}
	crossSum := sha256.Sum256([]byte(crossParts))

	depth := 5
	if len(runs) > 0 {
		if d, ok := asInt(runs[0]["depth_limit"]); ok {
			depth = d
		}
	}

	return Matrix{
		MatrixTag:      "cmb_v2",
		DepthLimit:     depth,
		Runs:           cleanRuns,
		ViolationTotal: violationTotal,
		CrossDigest:    hex.EncodeToString(crossSum[:]),
		RepeatStamp:    stamp,
	}, nil
}

func CheckBands(matrix Matrix) error {
	for _, row := range matrix.Runs {
		lo, _ := asInt(row["band_lo"])
		hi, _ := asInt(row["band_hi"])
		rows, _ := asInt(row["row_count"])
		if lo < 0 || hi > 255 {
			return fmt.Errorf("band out of documented range")
		}
		if rows < 1 {
			return fmt.Errorf("empty rows for %v", row["codename"])
		}
	}
	return nil
}

func MatrixClean(matrix Matrix) bool {
	if matrix.ViolationTotal != 0 {
		return false
	}
	for _, row := range matrix.Runs {
		v, _ := asInt(row["violation_rows"])
		if v != 0 {
			return false
		}
	}
	return true
}

func asInt(v any) (int, bool) {
	switch t := v.(type) {
	case int:
		return t, true
	case int64:
		return int(t), true
	case float64:
		return int(t), true
	default:
		return 0, false
	}
}
