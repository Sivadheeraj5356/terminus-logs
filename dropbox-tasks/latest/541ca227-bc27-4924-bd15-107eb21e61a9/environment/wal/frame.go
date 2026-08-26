package wal

import (
	"encoding/json"
	"os"
	"path/filepath"

	"linkenv/reg"
)

type Frame struct {
	Gen    uint64       `json:"gen"`
	Sealed bool         `json:"sealed"`
	Rows   []reg.RowRec `json:"rows"`
}

func walPath(root string) string {
	return filepath.Join(root, "wal.jsonl")
}

func Append(root string, fr Frame) error {
	if err := os.MkdirAll(root, 0o755); err != nil {
		return err
	}
	raw, err := json.Marshal(fr)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(walPath(root), os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(raw, '\n'))
	return err
}

func SealLatest(root string, gen uint64) error {
	path := walPath(root)
	raw, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var lines []string
	for _, line := range splitLines(raw) {
		if line == "" {
			continue
		}
		var fr Frame
		if err := json.Unmarshal([]byte(line), &fr); err != nil {
			return err
		}
		if fr.Gen == gen {
			fr.Sealed = true
		}
		b, err := json.Marshal(fr)
		if err != nil {
			return err
		}
		lines = append(lines, string(b))
	}
	out := append([]byte(nil), []byte(joinLines(lines))...)
	return os.WriteFile(path, out, 0o644)
}

func RecoverSealed(root string) (Frame, bool) {
	path := walPath(root)
	raw, err := os.ReadFile(path)
	if err != nil {
		return Frame{}, false
	}
	var tip Frame
	found := false
	for _, line := range splitLines(raw) {
		if line == "" {
			continue
		}
		var fr Frame
		if json.Unmarshal([]byte(line), &fr) != nil {
			continue
		}
		tip = fr
		found = true
	}
	return tip, found
}

func splitLines(raw []byte) []string {
	return stringSplit(string(raw))
}

func stringSplit(s string) []string {
	var lines []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			lines = append(lines, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		lines = append(lines, s[start:])
	}
	return lines
}

func joinLines(lines []string) string {
	if len(lines) == 0 {
		return ""
	}
	out := lines[0]
	for i := 1; i < len(lines); i++ {
		out += "\n" + lines[i]
	}
	return out + "\n"
}
