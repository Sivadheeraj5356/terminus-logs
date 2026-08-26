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
	marks := sys.explore(start)
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

// explore walks the state space with subsumption: states already dominated by
// a recorded state are not revisited, and a state that dominates a recorded
// one marks its strictly larger counters as saturated so the search stays
// finite on growing systems.
func (s *system) explore(start []int64) [][]int64 {
	seen := [][]int64{start}
	queue := [][]int64{start}
	for len(queue) > 0 {
		m := queue[0]
		queue = queue[1:]
		for _, rule := range s.rules {
			if !s.enabled(m, rule[0]) {
				continue
			}
			child := s.fireRule(m, rule[0], rule[1])
			skip := false
			for _, prev := range seen {
				if geq(prev, child) {
					skip = true
					break
				}
			}
			if skip {
				continue
			}
			for _, prev := range seen {
				if geq(child, prev) && !eq(child, prev) {
					for i := range child {
						if prev[i] != omega && child[i] != omega && child[i] > prev[i] {
							child[i] = omega
						}
					}
				}
			}
			seen = append(seen, child)
			queue = append(queue, child)
		}
	}
	return seen
}
