package setparse

import (
	"fmt"
	"strings"

	"helm-chart-coalesce/internal/yamlmini"
)

type Pair struct {
	Path  []string
	Value any
}

func Parse(arg string) (Pair, error) {
	eq := strings.Index(arg, "=")
	if eq < 0 {
		return Pair{}, fmt.Errorf("invalid --set %q", arg)
	}
	key := arg[:eq]
	valRaw := arg[eq+1:]
	path := strings.Split(key, ".")
	if len(path) == 0 {
		return Pair{}, fmt.Errorf("empty set key")
	}
	val, err := yamlmini.Parse("v: " + valRaw + "\n")
	if err != nil {
		return Pair{}, err
	}
	return Pair{Path: path, Value: val["v"]}, nil
}

func SetPath(m map[string]any, path []string, value any) map[string]any {
	if m == nil {
		m = map[string]any{}
	}
	if len(path) == 0 {
		return m
	}
	cur := m
	for i := 0; i < len(path)-1; i++ {
		next, ok := cur[path[i]].(map[string]any)
		if !ok {
			next = map[string]any{}
			cur[path[i]] = next
		}
		cur = next
	}
	cur[path[len(path)-1]] = value
	return m
}
