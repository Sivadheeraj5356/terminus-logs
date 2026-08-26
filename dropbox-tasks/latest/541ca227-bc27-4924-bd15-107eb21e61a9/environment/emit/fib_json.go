package emit

import (
	"encoding/json"
	"os"
	"path/filepath"

	"linkenv/reg"
)

type fibDoc struct {
	Rows       []reg.RowRec `json:"rows"`
	Fingerprint string      `json:"fingerprint"`
}

func WriteFib(outDir string, rows []reg.RowRec, fp string) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	doc := fibDoc{Rows: reg.ListSorted(rows), Fingerprint: fp}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(filepath.Join(outDir, "effective_fib.json"), raw, 0o644)
}

type LinkSlot struct {
	SlotID    string `json:"slot_id"`
	CarrierUp bool   `json:"carrier_up"`
	MirrorGen uint64 `json:"mirror_gen"`
}

type linkDoc struct {
	Probes []LinkSlot `json:"probes"`
}

func WriteLinkStatus(outDir string, probes []LinkSlot) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	doc := linkDoc{Probes: probes}
	raw, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	return os.WriteFile(filepath.Join(outDir, "link_status.json"), raw, 0o644)
}
