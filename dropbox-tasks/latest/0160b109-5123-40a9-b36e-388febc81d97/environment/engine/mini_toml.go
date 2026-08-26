package engine

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

// LoadArmOrder reads a simple arm order list from arm_ladder-like text by id.
func LoadArmOrder(path, armID string) ([]string, error) {
	meta, err := loadArmBlock(path, armID)
	if err != nil {
		return nil, err
	}
	raw, ok := meta["order"]
	if !ok {
		return nil, os.ErrNotExist
	}
	raw = strings.Trim(raw, "[]")
	parts := strings.Split(raw, ",")
	var out []string
	for _, p := range parts {
		p = strings.Trim(strings.TrimSpace(p), "\"")
		if p != "" {
			out = append(out, p)
		}
	}
	return out, nil
}

// LoadArmSalt returns the uint64 salt for an arm id.
func LoadArmSalt(path, armID string) (uint64, error) {
	meta, err := loadArmBlock(path, armID)
	if err != nil {
		return 0, err
	}
	raw, ok := meta["salt"]
	if !ok {
		return 0, nil
	}
	raw = strings.Trim(strings.TrimSpace(raw), "\"")
	return strconv.ParseUint(strings.TrimPrefix(raw, "0x"), 16, 64)
}

// LoadMutation returns touch id and delta_step for the first mutation block.
func LoadMutation(path string) (touch string, delta int, err error) {
	f, err := os.Open(path)
	if err != nil {
		return "", 0, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	inMut := false
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "[[mutations]]" {
			inMut = true
			continue
		}
		if strings.HasPrefix(line, "[[") {
			inMut = false
			continue
		}
		if !inMut {
			continue
		}
		if strings.HasPrefix(line, "touch = ") {
			touch = strings.Trim(strings.TrimPrefix(line, "touch = "), "\"")
		}
		if strings.HasPrefix(line, "delta_step = ") {
			delta, _ = strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "delta_step = ")))
		}
	}
	if touch == "" {
		return "", 0, os.ErrNotExist
	}
	return touch, delta, sc.Err()
}

func loadArmBlock(path, armID string) (map[string]string, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	cur := ""
	meta := map[string]string{}
	found := false
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "[[arms]]" {
			if found {
				return meta, nil
			}
			cur = ""
			meta = map[string]string{}
			continue
		}
		if strings.HasPrefix(line, "[[") {
			if found {
				return meta, nil
			}
			cur = ""
			continue
		}
		if strings.HasPrefix(line, "id = ") {
			cur = strings.Trim(strings.TrimPrefix(line, "id = "), "\"")
			if cur == armID {
				found = true
			}
			continue
		}
		if !found || cur != armID {
			continue
		}
		if strings.Contains(line, " = ") {
			parts := strings.SplitN(line, " = ", 2)
			if len(parts) == 2 {
				meta[parts[0]] = parts[1]
			}
		}
	}
	if found {
		return meta, sc.Err()
	}
	return nil, os.ErrNotExist
}
