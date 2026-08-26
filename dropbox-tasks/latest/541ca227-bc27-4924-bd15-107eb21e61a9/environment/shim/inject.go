package shim

import (
	"encoding/json"
	"os"

	"linkenv/reg"
)

type foreignRow struct {
	Key        string  `json:"key"`
	Prefix     string  `json:"prefix"`
	Via        string  `json:"via"`
	AdmitFence *uint64 `json:"admit_fence"`
}

type foreignDoc struct {
	Rows []foreignRow `json:"rows"`
}

type Injected struct {
	Row        reg.RowRec
	AdmitFence *uint64
}

func LoadInject(path string) ([]Injected, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var doc foreignDoc
	if err := json.Unmarshal(raw, &doc); err != nil {
		return nil, err
	}
	out := make([]Injected, 0, len(doc.Rows))
	for _, r := range doc.Rows {
		row := reg.RowRec{Key: r.Key, Prefix: r.Prefix, Via: r.Via, Class: reg.ClassInject}
		out = append(out, Injected{Row: row, AdmitFence: r.AdmitFence})
	}
	return out, nil
}
