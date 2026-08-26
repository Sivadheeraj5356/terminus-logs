package d1

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"mxbin/a6/b4"
	"mxbin/b2/c7"
)

func Fnv1a64Hex(data []byte) string {
	var h uint64 = 14695981039346656037
	for _, b := range data {
		h ^= uint64(b)
		h *= 1099511628211
	}
	return fmt.Sprintf("%016x", h)
}

func DigestOf(bound map[string]b4.Row) string {
	rows := make([]string, 0, len(bound))
	for id, r := range bound {
		rows = append(rows, fmt.Sprintf("%s|%s|%s|%d", id, r.Cloud, r.Actor, r.Gen))
	}
	sort.Strings(rows)
	text := strings.Join(rows, "\n")
	if len(rows) > 0 {
		text += "\n"
	}
	return Fnv1a64Hex([]byte(text))
}

func SealHex(runID, gate string, nHome int) string {
	return Fnv1a64Hex([]byte(fmt.Sprintf("%s|%s|%d", runID, gate, nHome)))
}

func Recover() error {
	_ = os.RemoveAll("/app/output/stage")
	_ = os.MkdirAll("/app/output/stage", 0o755)
	// Drop stale cache residue copies under scratch if present.
	scratch := "/app/environment/.scratch"
	_ = os.Remove(filepath.Join(scratch, "cache.mix"))
	return nil
}

func EnsureParent(path string) error {
	return os.MkdirAll(filepath.Dir(path), 0o755)
}

func loadBound(path string) (map[string]b4.Row, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	out := map[string]b4.Row{}
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		p := strings.Split(line, "|")
		if len(p) < 4 {
			continue
		}
		var g int
		fmt.Sscanf(p[3], "%d", &g)
		out[p[0]] = b4.Row{ID: p[0], Cloud: p[1], Actor: p[2], Gen: g}
	}
	return out, nil
}

func staleMix() string {
	dir := "/app/environment/fixtures/cache_stale"
	entries, err := os.ReadDir(dir)
	if err != nil {
		return ""
	}
	for _, e := range entries {
		if e.IsDir() {
			continue
		}
		raw, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			continue
		}
		for _, line := range strings.Split(string(raw), "\n") {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "mix:") {
				return strings.TrimSpace(strings.TrimPrefix(line, "mix:"))
			}
		}
	}
	return ""
}

func independentReplay(root string) (string, map[string]b4.Row, error) {
	sign := filepath.Join(root, "fixtures", "sign")
	m, err := b4.FoldCorrect(sign)
	if err != nil {
		return "", nil, err
	}
	bound := c7.BindCorrect(m, sign)
	return DigestOf(bound), bound, nil
}

func loadFresh(scratch string) ([]map[string]any, []map[string]string) {
	raw, err := os.ReadFile(filepath.Join(scratch, "fresh.rows"))
	if err != nil {
		return nil, nil
	}
	var fresh []map[string]any
	var classify []map[string]string
	for _, line := range strings.Split(string(raw), "\n") {
		line = strings.TrimSpace(line)
		if !strings.HasPrefix(line, "id:") {
			continue
		}
		parts := map[string]string{}
		for _, tok := range strings.Fields(line) {
			kv := strings.SplitN(tok, ":", 2)
			if len(kv) == 2 {
				parts[kv[0]] = kv[1]
			}
		}
		skew := 0
		fmt.Sscanf(parts["skew"], "%d", &skew)
		genN, span, touch := 0, 0, 0
		fmt.Sscanf(parts["gen_n"], "%d", &genN)
		fmt.Sscanf(parts["span"], "%d", &span)
		fmt.Sscanf(parts["touch"], "%d", &touch)
		fresh = append(fresh, map[string]any{
			"id": parts["id"], "skew": skew, "gen_n": genN, "span": span, "touch": touch,
		})
		band := "drift"
		if skew == 0 {
			band = "steady"
		}
		classify = append(classify, map[string]string{"id": parts["id"], "band": band})
	}
	return fresh, classify
}
