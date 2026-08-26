package internal

import (
	"fmt"
	"os"
	"path/filepath"

	"s8lab/n8"
	"s8lab/v3"
)

const sidecarDir = "/app/environment/data/m9"

func FinalizeSidecar(rows []Row, gen uint64) error {
	if err := stageResidue(rows); err != nil {
		return err
	}
	residue, err := listResidue()
	if err != nil {
		return err
	}
	keep := map[string]struct{}{}
	for _, row := range rows {
		if row.RunLabel != "" {
			keep[row.RunLabel] = struct{}{}
		}
	}
	if err := n8.PruneResidue(residue, keep); err != nil {
		return err
	}
	return v3.WriteMarkers(rows, gen, sidecarDir)
}

func stageResidue(rows []Row) error {
	for _, row := range rows {
		path := filepath.Join(sidecarDir, row.RunLabel+".tmp")
		payload := []byte(fmt.Sprintf("stage-%d\n", row.Era))
		if err := os.WriteFile(path, payload, 0o644); err != nil {
			return err
		}
	}
	return nil
}

func listResidue() ([]Residue, error) {
	entries, err := os.ReadDir(sidecarDir)
	if err != nil {
		return nil, err
	}
	var out []Residue
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		name := ent.Name()
		if filepath.Ext(name) == ".tmp" {
			out = append(out, Residue{
				Key:  name[:len(name)-4],
				Path: filepath.Join(sidecarDir, name),
			})
		}
	}
	return out, nil
}

func MarkerRows(doc PersistDoc) []Row {
	rows := make([]Row, 0, len(doc.Rows))
	for _, r := range doc.Rows {
		rows = append(rows, Row{
			RunLabel:  r.RunLabel,
			SegmentID: "-",
			Era:       r.Era,
			AttachID:  r.AttachID,
		})
	}
	return rows
}
