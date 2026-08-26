package peers

import (
	"fmt"
	"sort"
	"strconv"

	"splicekit/pkg/model"
)

type pairKey struct{ a, b string }

func canonPair(a, b string) pairKey {
	if a > b {
		return pairKey{a: b, b: a}
	}
	return pairKey{a: a, b: b}
}

// Rows builds settlement TSV rows and the mean share score.
func Rows(sc *model.Scenario, served []string) ([][]string, float64) {
	return share_y(sc, served)
}

func share_y(sc *model.Scenario, served []string) ([][]string, float64) {
	set := map[string]bool{}
	for _, s := range served {
		set[s] = true
	}
	elig := map[pairKey]int{}
	serv := map[pairKey]int{}
	for _, d := range sc.Demands {
		k := canonPair(d.PeerA, d.PeerB)
		elig[k] += d.Gbps
	}
	for _, d := range sc.Demands {
		if !set[d.ID] {
			continue
		}
		k := canonPair(d.PeerA, d.PeerB)
		serv[k] += d.Gbps
	}
	keys := make([]pairKey, 0, len(elig))
	for k := range elig {
		keys = append(keys, k)
	}
	sort.Slice(keys, func(i, j int) bool {
		if keys[i].a != keys[j].a {
			return keys[i].a < keys[j].a
		}
		return keys[i].b < keys[j].b
	})
	var rows [][]string
	sumShare := 0.0
	n := 0
	for _, k := range keys {
		share := 0.0
		if elig[k] > 0 {
			share = float64(serv[k]) / float64(elig[k])
		}
		rows = append(rows, []string{
			k.a, k.b,
			strconv.Itoa(serv[k]),
			strconv.Itoa(elig[k]),
			fmt.Sprintf("%.4f", share),
		})
		sumShare += share
		n++
	}
	avg := 0.0
	if n > 0 {
		avg = sumShare / float64(n)
	}
	return rows, avg
}
