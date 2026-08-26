#!/usr/bin/env bash
# PLAN:
# 1. Replace the analysis with a decision procedure that is exact and always
#    terminates on unbounded systems: explore the reachable behaviour as a
#    tree, and when a branch strictly dominates one of its own ancestors,
#    saturate the strictly-grown counters so unbounded growth is represented
#    finitely; answer each query against the explored summary states.
# 2. Rebuild the module.
# 3. Run every sample job so the verdicts are visible.
set -e

cat > /app/analysis/analysis.go <<'EOF_ANALYSIS'
// Package analysis decides cover queries for counter systems against the
// contract in /app/docs/spec.md.
package analysis

import (
	"errors"

	"coverd/model"
)

var errMalformed = errors.New("job does not conform to the analysis contract")

const (
	valMax   = int64(1000)
	omega    = int64(-1)
	maxN     = 12
	maxRules = 16
	maxQuery = 32
)

type system struct {
	n     int
	rules [][2][]int64
}

// Run validates one job and answers its cover queries.
func Run(job model.Job) ([]bool, error) {
	if job.Counters == nil || *job.Counters < 1 || *job.Counters > maxN {
		return nil, errMalformed
	}
	n := int(*job.Counters)
	if job.Rules == nil || len(*job.Rules) > maxRules {
		return nil, errMalformed
	}
	sys := &system{n: n}
	for _, r := range *job.Rules {
		take, err := vec(r.Take, n)
		if err != nil {
			return nil, err
		}
		give, err := vec(r.Give, n)
		if err != nil {
			return nil, err
		}
		sys.rules = append(sys.rules, [2][]int64{take, give})
	}
	start, err := vec(job.Start, n)
	if err != nil {
		return nil, err
	}
	if job.Queries == nil || len(*job.Queries) > maxQuery {
		return nil, errMalformed
	}
	var queries [][]int64
	for _, q := range *job.Queries {
		qv := q
		checked, err := vec(&qv, n)
		if err != nil {
			return nil, err
		}
		queries = append(queries, checked)
	}
	marks := sys.coverTree(start)
	covered := make([]bool, 0, len(queries))
	for _, q := range queries {
		covered = append(covered, anyGeq(marks, q))
	}
	return covered, nil
}

func vec(v *[]int64, n int) ([]int64, error) {
	if v == nil || len(*v) != n {
		return nil, errMalformed
	}
	for _, x := range *v {
		if x < 0 || x > valMax {
			return nil, errMalformed
		}
	}
	out := make([]int64, n)
	copy(out, *v)
	return out, nil
}

func geq(a, b []int64) bool {
	for i := range a {
		if a[i] != omega && (b[i] == omega || a[i] < b[i]) {
			return false
		}
	}
	return true
}

func eq(a, b []int64) bool {
	for i := range a {
		if a[i] != b[i] {
			return false
		}
	}
	return true
}

func anyGeq(marks [][]int64, q []int64) bool {
	for _, m := range marks {
		if geq(m, q) {
			return true
		}
	}
	return false
}

func (s *system) enabled(m, take []int64) bool {
	for i := range m {
		if m[i] != omega && m[i] < take[i] {
			return false
		}
	}
	return true
}

func (s *system) fireRule(m, take, give []int64) []int64 {
	out := make([]int64, s.n)
	for i := range m {
		if m[i] == omega {
			out[i] = omega
		} else {
			out[i] = m[i] - take[i] + give[i]
		}
	}
	return out
}

// accelerate marks as unbounded every coordinate strictly above some
// dominated ancestor on the current path.
func accelerate(m []int64, path [][]int64) []int64 {
	out := make([]int64, len(m))
	copy(out, m)
	for _, anc := range path {
		if geq(out, anc) && !eq(out, anc) {
			for i := range out {
				if anc[i] != omega && out[i] != omega && out[i] > anc[i] {
					out[i] = omega
				}
			}
		}
	}
	return out
}

type node struct {
	m    []int64
	path [][]int64
}

// coverTree builds the classic coverability tree: a branch stops when its
// marking repeats an ancestor on its own path; no cross-branch pruning.
func (s *system) coverTree(start []int64) [][]int64 {
	var marks [][]int64
	stack := []node{{m: start, path: nil}}
	for len(stack) > 0 {
		nd := stack[len(stack)-1]
		stack = stack[:len(stack)-1]
		marks = append(marks, nd.m)
		newpath := make([][]int64, len(nd.path)+1)
		copy(newpath, nd.path)
		newpath[len(nd.path)] = nd.m
		for _, rule := range s.rules {
			if !s.enabled(nd.m, rule[0]) {
				continue
			}
			child := accelerate(s.fireRule(nd.m, rule[0], rule[1]), newpath)
			onPath := false
			for _, anc := range newpath {
				if eq(child, anc) {
					onPath = true
					break
				}
			}
			if onPath {
				marks = append(marks, child)
				continue
			}
			stack = append(stack, node{m: child, path: newpath})
		}
	}
	return marks
}
EOF_ANALYSIS

cd /app && go build

for job in /app/samples/*.job.json; do
	echo "== $job"
	go run . < "$job"
done