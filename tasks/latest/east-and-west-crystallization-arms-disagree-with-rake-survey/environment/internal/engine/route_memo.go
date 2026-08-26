package engine

import (
	"encoding/json"
	"os"
	"strconv"
)

const memoPath = "/app/output/.sector_memo.json"

func memoLoad() map[string]string {
	raw, err := os.ReadFile(memoPath)
	if err != nil {
		return map[string]string{}
	}
	out := map[string]string{}
	_ = json.Unmarshal(raw, &out)
	if out == nil {
		return map[string]string{}
	}
	return out
}

func memoStore(m map[string]string) {
	_ = os.MkdirAll("/app/output", 0o755)
	raw, err := json.Marshal(m)
	if err != nil {
		return
	}
	_ = os.WriteFile(memoPath, raw, 0o644)
}

func memoKey(_ string, sec int) string {
	return strconv.Itoa(sec)
}

func memoGet(pondID string, sec int) (string, bool) {
	m := memoLoad()
	v, ok := m[memoKey(pondID, sec)]
	return v, ok
}

func memoPut(pondID string, sec int, arm string) {
	m := memoLoad()
	m[memoKey(pondID, sec)] = arm
	memoStore(m)
}
