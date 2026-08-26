package bvm

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

type manifest struct {
	Op     string   `json:"op"`
	Base   string   `json:"base"`
	Models []string `json:"models"`
}

// RunBatch processes a manifest of modules under a single op (verify or run)
// and prints one report line per module followed by an FNV-1a-32 digest.
func RunBatch(path string) (string, error) {
	if path == "" {
		return "", errType("missing --manifest")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return "", err
	}
	var mf manifest
	if err := json.Unmarshal(data, &mf); err != nil {
		return "", errType("bad manifest: %v", err)
	}
	if mf.Op == "" {
		mf.Op = "verify"
	}
	dir := filepath.Dir(path)
	base := mf.Base
	if base == "" {
		base = dir
	} else if !filepath.IsAbs(base) {
		base = filepath.Join(dir, base)
	}
	var lines []string
	for _, rel := range mf.Models {
		p := rel
		if !filepath.IsAbs(p) {
			p = filepath.Join(base, rel)
		}
		name := strings.TrimSuffix(filepath.Base(rel), ".bvm")
		src, err := os.ReadFile(p)
		if err != nil {
			lines = append(lines, fmt.Sprintf("%s: error", name))
			continue
		}
		m, err := Parse(string(src))
		if err != nil {
			lines = append(lines, fmt.Sprintf("%s: parse-error", name))
			continue
		}
		switch mf.Op {
		case "verify":
			allOK := true
			for fi := range m.Funcs {
				if !verifyFunc(m, &m.Funcs[fi]).ok {
					allOK = false
					break
				}
			}
			if allOK {
				lines = append(lines, name+": verified")
			} else {
				lines = append(lines, name+": rejected")
			}
		case "run":
			out, err := RunModule(m, false)
			if err != nil {
				lines = append(lines, name+": error")
			} else {
				lines = append(lines, name+": "+out)
			}
		default:
			return "", errType("unknown batch op %q", mf.Op)
		}
	}
	body := strings.Join(lines, "\n")
	if body != "" {
		body += "\n"
	}
	return body + "digest: " + fnv1a32(strings.Join(lines, "\n")), nil
}
