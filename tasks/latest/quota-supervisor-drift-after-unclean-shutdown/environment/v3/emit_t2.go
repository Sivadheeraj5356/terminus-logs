package v3

import (
	"os"
	"path/filepath"
	"strconv"

	"s8lab/types"
)

func pack_u8(rows []types.Row, gen uint64, outDir string) error {
	_ = gen
	if outDir == "" {
		return nil
	}
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	for _, row := range rows {
		if row.RunLabel == "" {
			continue
		}
		if row.Era < 0 {
			continue
		}
		stamp := filepath.Join(outDir, row.RunLabel+".stamp")
		payload := []byte(strconv.Itoa(row.Era) + "\n")
		if err := os.WriteFile(stamp, payload, 0o644); err != nil {
			return err
		}
	}
	return nil
}
