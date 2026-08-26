package lib

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func EnvRoot() string {
	if v := os.Getenv("OV_ROOT"); v != "" {
		return v
	}
	return "/app/environment"
}

func ConfPath() string {
	return filepath.Join(EnvRoot(), "conf", "workspace.conf")
}

func CaseDir() string {
	return filepath.Join(EnvRoot(), "cases")
}

func MaskPath() string {
	return filepath.Join(EnvRoot(), "var", "mig", "epoch_mask.json")
}

func StampPath() string {
	return filepath.Join(EnvRoot(), "var", "mig", "seal_stamp.json")
}

func GenPath() string {
	return filepath.Join(EnvRoot(), "var", "mig", "suite_gen")
}

func IdxPath() string {
	return filepath.Join(CaseDir(), "idx.json")
}

func SlotValues() ([]int, error) {
	f, err := os.Open(ConfPath())
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []int
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if strings.HasPrefix(line, "slot=") {
			n, _ := strconv.Atoi(strings.TrimPrefix(line, "slot="))
			out = append(out, n)
		}
	}
	return out, sc.Err()
}

func SlotSum() int {
	vals, err := SlotValues()
	if err != nil {
		return 0
	}
	total := 0
	for _, v := range vals {
		total += v
	}
	return total
}

func SlotWeight() int {
	vals, err := SlotValues()
	if err != nil {
		return 0
	}
	return len(vals)
}

func ReadMask() int {
	b, err := os.ReadFile(MaskPath())
	if err != nil {
		return 0
	}
	var obj struct {
		Mask int `json:"mask"`
	}
	if json.Unmarshal(b, &obj) != nil {
		return 0
	}
	return obj.Mask
}

func ReadCycle() int {
	b, err := os.ReadFile(GenPath())
	if err != nil {
		return 0
	}
	n, _ := strconv.Atoi(strings.TrimSpace(string(b)))
	return n
}
