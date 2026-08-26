package engine

import (
	"encoding/json"
	"os"
)

// ResumeState carries a mid-tape continuation seed.
type ResumeState struct {
	CursorDay  int                `json:"cursor_day"`
	CursorTick int                `json:"cursor_tick"`
	LastCmd    map[string]float64 `json:"last_cmd"`
	Fronts     map[string]float64 `json:"fronts"`
}

func LoadResume(path string) (ResumeState, bool) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return ResumeState{}, false
	}
	var st ResumeState
	if err := json.Unmarshal(raw, &st); err != nil {
		return ResumeState{}, false
	}
	if st.LastCmd == nil {
		st.LastCmd = map[string]float64{}
	}
	if st.Fronts == nil {
		st.Fronts = map[string]float64{}
	}
	return st, true
}

func afterCursor(day, tick, cDay, cTick int) bool {
	if day > cDay {
		return true
	}
	if day < cDay {
		return false
	}
	return tick > cTick
}
