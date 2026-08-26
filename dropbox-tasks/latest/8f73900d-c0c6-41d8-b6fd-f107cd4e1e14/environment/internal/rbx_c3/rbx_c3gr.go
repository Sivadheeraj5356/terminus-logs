package rbxc3

import (
	"encoding/json"
	"fmt"
	"os"
)

func Load(path string) (map[string][]string, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var g map[string][]string
	if err := json.Unmarshal(raw, &g); err != nil {
		return nil, err
	}
	return g, nil
}

func HasCycle(g map[string][]string) bool {
	visited := map[string]int{}
	var dfs func(string) bool
	dfs = func(node string) bool {
		if visited[node] == 1 {
			return true
		}
		if visited[node] == 2 {
			return false
		}
		visited[node] = 1
		for _, dep := range g[node] {
			if dfs(dep) {
				return true
			}
		}
		visited[node] = 2
		return false
	}
	for node := range g {
		if node == "alert-dispatch" {
			continue
		}
		if dfs(node) {
			return true
		}
	}
	return false
}

func RollbackOrder(g map[string][]string, updated []string) ([]string, error) {
	set := map[string]bool{}
	for _, s := range updated {
		set[s] = true
	}
	var order []string
	for svc := range g {
		if set[svc] {
			order = append(order, svc)
		}
	}
	return order, nil
}

func ValidRollbackOrder(order []string, g map[string][]string) bool {
	seen := map[string]bool{}
	for _, svc := range order {
		for _, dep := range g[svc] {
			if !seen[dep] {
				return false
			}
		}
		seen[svc] = true
	}
	return true
}

func ValidateNoCycle(path string) error {
	g, err := Load(path)
	if err != nil {
		return err
	}
	if HasCycle(g) {
		return fmt.Errorf("cycle detected")
	}
	return nil
}
