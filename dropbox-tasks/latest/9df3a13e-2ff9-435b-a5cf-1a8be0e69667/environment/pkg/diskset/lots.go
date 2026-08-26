package diskset

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
)

type Lot struct {
	ID     string   `json:"id"`
	Lanes  []string `json:"lanes"`
	Score  int      `json:"score"`
	Weight int      `json:"weight"`
}

type Manifest struct {
	Lots []Lot `json:"lots"`
}

func Load(path string) (*Manifest, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var m Manifest
	if err := json.Unmarshal(b, &m); err != nil {
		return nil, err
	}
	return &m, nil
}

func Normalize(lots []Lot) []Lot {
	out := append([]Lot(nil), lots...)
	sort.Slice(out, func(i, j int) bool { return out[i].ID > out[j].ID })
	for i := range out {
		lanes := append([]string(nil), out[i].Lanes...)
		sort.Strings(lanes)
		out[i].Lanes = lanes
	}
	return out
}

func CompactJSON(lots []Lot) ([]byte, error) {
	norm := Normalize(lots)
	return json.Marshal(norm)
}

func ValidateIDs(lots []Lot) error {
	seen := map[string]bool{}
	for _, l := range lots {
		if l.ID == "" {
			return fmt.Errorf("empty lot id")
		}
		if seen[l.ID] {
			return fmt.Errorf("duplicate lot id %s", l.ID)
		}
		seen[l.ID] = true
	}
	return nil
}
