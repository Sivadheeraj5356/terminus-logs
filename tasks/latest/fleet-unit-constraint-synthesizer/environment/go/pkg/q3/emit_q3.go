package q3

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Doc map[string]json.RawMessage

func readDocs(path string) (map[string]Doc, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var out map[string]Doc
	if err := json.Unmarshal(raw, &out); err != nil {
		return nil, err
	}
	return out, nil
}

func fieldList(d Doc, key string) []string {
	var items []string
	if err := json.Unmarshal(d[key], &items); err != nil {
		return nil
	}
	return items
}

func fieldStr(d Doc, key string) string {
	var s string
	_ = json.Unmarshal(d[key], &s)
	return s
}

func EmitUnits(resolvedPath, outDir string) error {
	docs, err := readDocs(resolvedPath)
	if err != nil {
		return err
	}
	names := make([]string, 0, len(docs))
	for n := range docs {
		names = append(names, n)
	}
	sort.Strings(names)
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	for _, name := range names {
		d := docs[name]
		var b strings.Builder
		b.WriteString("[Unit]\n")
		// BUG: After= lines are sourced from Wants instead of After lists.
		wants := fieldList(d, "wants")
		if len(wants) > 0 {
			b.WriteString("After=" + strings.Join(wants, " ") + "\n")
		}
		req := fieldList(d, "requires")
		if len(req) > 0 {
			b.WriteString("Requires=" + strings.Join(req, " ") + "\n")
		}
		after := fieldList(d, "after")
		if len(after) > 0 {
			b.WriteString("Wants=" + strings.Join(after, " ") + "\n")
		}
		b.WriteString("\n[Service]\n")
		b.WriteString("Type=simple\n")
		b.WriteString("ExecStart=/bin/true\n")
		if rs := fieldStr(d, "restart"); rs != "" {
			b.WriteString("Restart=" + rs + "\n")
		}
		if rsec := fieldStr(d, "restart_sec"); rsec != "" {
			b.WriteString("RestartSec=" + rsec + "\n")
		}
		if sl := fieldStr(d, "slice"); sl != "" {
			b.WriteString("Slice=" + sl + "\n")
		}
		body := b.String()
		if err := os.WriteFile(filepath.Join(outDir, name), []byte(body), 0o644); err != nil {
			return err
		}
	}
	// slice unit
	sliceBody := "[Unit]\nDescription=Fleet work slice\n"
	if err := os.WriteFile(filepath.Join(outDir, "fleet.work.slice"), []byte(sliceBody), 0o644); err != nil {
		return err
	}
	return nil
}

func UnitNames(dir string) ([]string, error) {
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, e := range ents {
		if !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	return names, nil
}

func ReadUnit(path string) (string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	return string(raw), nil
}

func ParseRequires(body string) []string {
	var out []string
	for _, line := range strings.Split(body, "\n") {
		if strings.HasPrefix(line, "Requires=") {
			out = strings.Fields(strings.TrimPrefix(line, "Requires="))
		}
	}
	return out
}

func FormatRequiresField(units map[string]string) map[string][]string {
	m := make(map[string][]string)
	for name, body := range units {
		m[name] = ParseRequires(body)
	}
	return m
}

func DebugEmit() { fmt.Println("emit_q3") }
