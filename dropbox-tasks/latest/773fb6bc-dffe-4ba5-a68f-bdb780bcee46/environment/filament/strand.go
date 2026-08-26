package filament

import (
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

func ListForeign(ws string) ([]string, error) {
	dir := filepath.Join(ws, "foreign")
	ents, err := os.ReadDir(dir)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	names := make([]string, 0, len(ents))
	for _, e := range ents {
		if !e.IsDir() {
			names = append(names, e.Name())
		}
	}
	sort.Strings(names)
	out := make([]string, 0, len(names))
	for _, n := range names {
		out = append(out, fmt.Sprintf("foreign/%s", n))
	}
	return out, nil
}
