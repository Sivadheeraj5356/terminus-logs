package arms

import (
	"os"
	"strings"
)

type Row struct {
	ID   string
	From string
	To   string
}

func Parse(path string) ([]Row, []string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, nil, err
	}
	var rows []Row
	var ids []string
	var cur Row
	flush := func() {
		if cur.ID != "" || cur.From != "" || cur.To != "" {
			rows = append(rows, cur)
			cur = Row{}
		}
	}
	for _, ln := range strings.Split(string(raw), "\n") {
		s := strings.TrimSpace(ln)
		if s == "[[arms]]" {
			flush()
			continue
		}
		if strings.HasPrefix(s, "id") {
			cur.ID = stripAssign(s)
			ids = append(ids, cur.ID)
		} else if strings.HasPrefix(s, "from") {
			cur.From = stripAssign(s)
		} else if strings.HasPrefix(s, "to") {
			cur.To = stripAssign(s)
		}
	}
	flush()
	return rows, ids, nil
}

// Remap walks rotation arms to a fixpoint.
func Remap(start []string, rows []Row) []string {
	m := map[string]string{}
	for _, r := range rows {
		if r.From != "" && r.To != "" {
			m[r.From] = r.To
		}
	}
	out := append([]string{}, start...)
	for range 64 {
		changed := false
		for i, k := range out {
			if v, ok := m[k]; ok && v != k {
				out[i] = v
				changed = true
			}
		}
		if !changed {
			break
		}
	}
	return out
}

func stripAssign(s string) string {
	parts := strings.SplitN(s, "=", 2)
	if len(parts) != 2 {
		return ""
	}
	return strings.Trim(strings.TrimSpace(parts[1]), `"`)
}
