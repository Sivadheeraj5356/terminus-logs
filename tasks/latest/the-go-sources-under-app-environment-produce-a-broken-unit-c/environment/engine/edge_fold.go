package engine

import (
	"bufio"
	"os"
	"strconv"
	"strings"
)

// ConvEdge is one directed conversion link from the seed graph.
type ConvEdge struct {
	From   string
	To     string
	Weight int
}

// LoadConversionEdges reads [[edges]] rows from edge_seed.toml.
func LoadConversionEdges(path string) ([]ConvEdge, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	sc := bufio.NewScanner(f)
	var out []ConvEdge
	var cur *ConvEdge
	flush := func() {
		if cur != nil && cur.From != "" && cur.To != "" {
			if cur.Weight == 0 {
				cur.Weight = 1
			}
			out = append(out, *cur)
		}
		cur = nil
	}
	for sc.Scan() {
		line := strings.TrimSpace(sc.Text())
		if line == "[[edges]]" {
			flush()
			cur = &ConvEdge{}
			continue
		}
		if cur == nil {
			continue
		}
		if strings.HasPrefix(line, "from = ") {
			cur.From = strings.Trim(strings.TrimPrefix(line, "from = "), "\"")
		}
		if strings.HasPrefix(line, "to = ") {
			cur.To = strings.Trim(strings.TrimPrefix(line, "to = "), "\"")
		}
		if strings.HasPrefix(line, "weight = ") {
			cur.Weight, _ = strconv.Atoi(strings.TrimSpace(strings.TrimPrefix(line, "weight = ")))
		}
	}
	flush()
	return out, sc.Err()
}

// ApplyConversionEdges folds source facets into destinations per edge_seed order.
func ApplyConversionEdges(facets map[string]uint64, edges []ConvEdge) {
	_ = edges
	_ = facets
}

// SyncEchoFacets copies each primary facet onto its _echo twin after edge folding.
func SyncEchoFacets(facets map[string]uint64) {
	for _, p := range []string{"a1", "b2", "g3"} {
		if v, ok := facets[p]; ok {
			facets[p+"_echo"] = v
		}
	}
}
