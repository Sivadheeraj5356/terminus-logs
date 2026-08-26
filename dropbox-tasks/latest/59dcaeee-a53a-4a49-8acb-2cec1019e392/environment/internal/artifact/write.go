package artifact

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"rfimhyst/internal/contract"
)

var artifactNames = []string{"trajectory.tsv", "avalanches.jsonl", "checkpoint.json"}

func Cleanup(dir string) {
	for _, name := range artifactNames {
		_ = os.Remove(filepath.Join(dir, name))
		_ = os.Remove(filepath.Join(dir, "."+name+".tmp"))
	}
}

func StateDigest(model *contract.RuntimeModel, states []int) string {
	var builder strings.Builder
	for i, spin := range model.Spins {
		fmt.Fprintf(&builder, "%s\t%d\n", spin.ID, states[i])
	}
	sum := sha256.Sum256([]byte(builder.String()))
	return hex.EncodeToString(sum[:])
}

func AvalancheLine(record contract.AvalancheRecord) ([]byte, error) {
	line, err := json.Marshal(record)
	if err != nil {
		return nil, err
	}
	return append(line, '\n'), nil
}

func CheckpointBytes(cp contract.Checkpoint) ([]byte, error) {
	data, err := json.MarshalIndent(cp, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}

func AtomicWrite(dir string, trajectory, avalanches, checkpoint []byte) error {
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	files := []struct {
		name string
		data []byte
	}{
		{"trajectory.tsv", trajectory},
		{"avalanches.jsonl", avalanches},
		{"checkpoint.json", checkpoint},
	}
	for _, file := range files {
		tmp := filepath.Join(dir, "."+file.name+".tmp")
		if err := os.WriteFile(tmp, file.data, 0o644); err != nil {
			Cleanup(dir)
			return err
		}
	}
	for _, file := range files {
		if err := os.Rename(filepath.Join(dir, "."+file.name+".tmp"), filepath.Join(dir, file.name)); err != nil {
			Cleanup(dir)
			return err
		}
	}
	return nil
}
