package state

import (
	"encoding/json"
	"os"
)

const StateVersion = 2

type ReplayState struct {
	StateVersion int    `json:"state_version"`
	InputHash    string `json:"input_hash"`
	RowCount     int    `json:"row_count"`
	SensorCount  int    `json:"sensor_count"`
	BucketCount  int    `json:"bucket_count"`
}

func Load(path string) (*ReplayState, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var st ReplayState
	if err := json.Unmarshal(data, &st); err != nil {
		return nil, err
	}
	return &st, nil
}

func Compatible(st *ReplayState, hash string) bool {
	if st == nil {
		return false
	}
	return st.StateVersion == StateVersion && st.InputHash == hash
}
