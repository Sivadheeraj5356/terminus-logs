package main

import (
	"bufio"
	"fmt"
	"math"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

const v2 = -1

var v1 = math.Inf(-1)

func q4(a, b float64) float64 {
	if math.IsInf(a, -1) {
		return b
	}
	if math.IsInf(b, -1) {
		return a
	}
	if a < b {
		a, b = b, a
	}
	return a + math.Log1p(math.Exp(b-a))
}

func q3(x float64) float64 {
	if x <= 0 {
		return v1
	}
	return math.Log(x)
}

type t1 struct {
	id      string
	n, k, t int
	dmax    int
	seed    uint64
	pi      []float64
	a       [][]float64
	b       [][]float64
	d       [][]float64
	m       []float64
}

type t2 struct {
	n, dmax      int
	f4         [][]float64
	f5         [][]float64
	f6           []float64
	f3, f2 [][]float64 
	f1     [][]float64 
}

func q1(c *t1) *t2 {
	m := &t2{n: c.n, dmax: c.dmax, f6: c.m}
	m.f4 = make([][]float64, c.n)
	m.f5 = make([][]float64, c.n)
	m.f3 = make([][]float64, c.n)
	m.f2 = make([][]float64, c.n)
	m.f1 = make([][]float64, c.n)
	for i := 0; i < c.n; i++ {
		m.f4[i] = make([]float64, c.n)
		for j := 0; j < c.n; j++ {
			m.f4[i][j] = q3(c.a[i][j])
		}
		m.f5[i] = make([]float64, c.k)
		for k := 0; k < c.k; k++ {
			m.f5[i][k] = q3(c.b[i][k])
		}
		m.f3[i] = make([]float64, c.dmax+1)
		m.f2[i] = make([]float64, c.dmax+1)
		m.f1[i] = make([]float64, c.dmax)
		surv := make([]float64, c.dmax+2)
		acc := 0.0
		for d := c.dmax; d >= 1; d-- {
			acc += c.d[i][d-1]
			surv[d] = acc
		}
		mean := 0.0
		for d := 1; d <= c.dmax; d++ {
			mean += float64(d) * c.d[i][d-1]
		}
		for u := 1; u <= c.dmax; u++ {
			m.f1[i][u-1] = v1
			if surv[u] <= 0 {
				m.f3[i][u] = v1
				m.f2[i][u] = v1
				continue
			}
			m.f3[i][u] = q3(c.d[i][u-1] / surv[u])
			m.f2[i][u] = q3(surv[u+1] / surv[u])
			lp := q3(c.pi[i])
			if !math.IsInf(lp, -1) {
				m.f1[i][u-1] = lp + q3(surv[u]/mean)
			}
		}
	}
	return m
}
func (m *t2) q5(obs []int, t, s int) float64 {
	if obs[t] == v2 {
		return q3(m.f6[s])
	}
	return q3(1.0-m.f6[s]) + m.f5[s][obs[t]]
}

func (m *t2) q7(obs []int) (float64, [][]float64, float64) {
	n, dmax := m.n, m.dmax
	t := len(obs)
	la := make([][][]float64, t)
	lb := make([][][]float64, t)
	for s := 0; s < t; s++ {
		la[s] = make([][]float64, n)
		lb[s] = make([][]float64, n)
		for i := 0; i < n; i++ {
			la[s][i] = make([]float64, dmax)
			lb[s][i] = make([]float64, dmax)
			for u := 0; u < dmax; u++ {
				la[s][i][u] = v1
				lb[s][i][u] = v1
			}
		}
	}
	for i := 0; i < n; i++ {
		e0 := m.q5(obs, 0, i)
		for u := 0; u < dmax; u++ {
			if !math.IsInf(m.f1[i][u], -1) {
				la[0][i][u] = m.f1[i][u] + e0
			}
		}
	}
	for s := 1; s < t; s++ {
		prev, cur := la[s-1], la[s]
		exit := make([]float64, n)
		for i := 0; i < n; i++ {
			acc := v1
			for u := 1; u <= dmax; u++ {
				v := prev[i][u-1]
				if !math.IsInf(v, -1) && !math.IsInf(m.f3[i][u], -1) {
					acc = q4(acc, v+m.f3[i][u])
				}
			}
			if !math.IsInf(acc, -1) {
				acc += m.q5(obs, s, i) 
			}
			exit[i] = acc
		}
		for j := 0; j < n; j++ {
			acc := v1
			for i := 0; i < n; i++ {
				if !math.IsInf(exit[i], -1) && !math.IsInf(m.f4[i][j], -1) {
					acc = q4(acc, exit[i]+m.f4[i][j])
				}
			}
			cur[j][0] = acc
			eStay := m.q5(obs, s, j)
			for u := 1; u < dmax; u++ {
				v := prev[j][u-1]
				if !math.IsInf(v, -1) && !math.IsInf(m.f2[j][u], -1) {
					cur[j][u] = v + m.f2[j][u] + eStay
				}
			}
		}
	}
	loglik := v1
	for i := 0; i < n; i++ {
		for u := 0; u < dmax; u++ {
			loglik = q4(loglik, la[t-1][i][u])
		}
	}

	for i := 0; i < n; i++ {
		for u := 0; u < dmax; u++ {
			lb[t-1][i][u] = 0
		}
	}
	for s := t - 2; s >= 0; s-- {
		nxt, cur := lb[s+1], lb[s]
		jumpc := make([]float64, n)
		for i := 0; i < n; i++ {
			acc := v1
			for j := 0; j < n; j++ {
				if !math.IsInf(nxt[j][0], -1) && !math.IsInf(m.f4[i][j], -1) {
					acc = q4(acc, m.f4[i][j]+nxt[j][0])
				}
			}
			jumpc[i] = acc
		}
		for i := 0; i < n; i++ {
			eI := m.q5(obs, s+1, i) 
			for u := 1; u <= dmax; u++ {
				stay := v1
				if u < dmax && !math.IsInf(m.f2[i][u], -1) &&
					!math.IsInf(nxt[i][u], -1) {
					stay = m.f2[i][u] + nxt[i][u]
				}
				jump := v1
				if !math.IsInf(m.f3[i][u], -1) && !math.IsInf(jumpc[i], -1) {
					jump = m.f3[i][u] + jumpc[i]
				}
				v := q4(stay, jump)
				if !math.IsInf(v, -1) {
					v += eI
				}
				cur[i][u-1] = v
			}
		}
	}

	gamma := make([][]float64, t)
	for s := 0; s < t; s++ {
		gamma[s] = make([]float64, n)
		for i := 0; i < n; i++ {
			acc := v1
			for u := 0; u < dmax; u++ {
				va, vb := la[s][i][u], lb[s][i][u]
				if !math.IsInf(va, -1) && !math.IsInf(vb, -1) {
					acc = q4(acc, va+vb)
				}
			}
			if math.IsInf(acc, -1) {
				gamma[s][i] = 0
			} else {
				gamma[s][i] = math.Exp(acc - loglik)
			}
		}
	}

	nseg := 1.0
	for s := 0; s < t-1; s++ {
		acc := v1
		for i := 0; i < n; i++ {
			ex := v1
			for u := 1; u <= dmax; u++ {
				v := la[s][i][u-1]
				if !math.IsInf(v, -1) && !math.IsInf(m.f3[i][u], -1) {
					ex = q4(ex, v+m.f3[i][u])
				}
			}
			if math.IsInf(ex, -1) {
				continue
			}
			ex += m.q5(obs, s+1, i)
			for j := 0; j < n; j++ {
				if !math.IsInf(lb[s+1][j][0], -1) && !math.IsInf(m.f4[i][j], -1) {
					acc = q4(acc, ex+m.f4[i][j]+lb[s+1][j][0])
				}
			}
		}
		if !math.IsInf(acc, -1) {
			nseg += math.Exp(acc - loglik)
		}
	}
	return loglik, gamma, nseg
}


type t3 struct{ z uint64 }

func (r *t3) q10() uint64 {
	r.z += 0x9E3779B97F4A7C15
	x := r.z
	x = (x ^ (x >> 30)) * 0xBF58476D1CE4E5B9
	x = (x ^ (x >> 27)) * 0x94D049BB133111EB
	return x ^ (x >> 31)
}

func (r *t3) q11() float64 {
	return float64(r.q10()>>11) / (1 << 53)
}

func q9(u float64, w []float64) int {
	acc := 0.0
	for i, v := range w {
		acc += v
		if u < acc {
			return i
		}
	}
	return len(w) - 1
}
func q8(c *t1) []int {
	rng := &t3{z: c.seed}
	surv := make([][]float64, c.n)
	mean := make([]float64, c.n)
	for i := 0; i < c.n; i++ {
		surv[i] = make([]float64, c.dmax+2)
		acc := 0.0
		for d := c.dmax; d >= 1; d-- {
			acc += c.d[i][d-1]
			surv[i][d] = acc
		}
		for d := 1; d <= c.dmax; d++ {
			mean[i] += float64(d) * c.d[i][d-1]
		}
	}
	state := q9(rng.q11(), c.pi)
	offw := make([]float64, c.dmax)
	for u := 1; u <= c.dmax; u++ {
		offw[u-1] = surv[state][u] / mean[state]
	}
	elapsed := q9(rng.q11(), offw) + 1
	condw := make([]float64, c.dmax)
	for d := elapsed; d <= c.dmax; d++ {
		condw[d-1] = c.d[state][d-1] / surv[state][elapsed]
	}
	total := q9(rng.q11(), condw) + 1
	remaining := total - elapsed + 1

	states := make([]int, c.t)
	for t := 0; t < c.t; t++ {
		states[t] = state
		remaining--
		if remaining == 0 {
			state = q9(rng.q11(), c.a[state])
			remaining = q9(rng.q11(), c.d[state]) + 1
		}
	}
	obs := make([]int, c.t)
	for t := 0; t < c.t; t++ {
		s := states[t]
		if t >= 1 {
			s = states[t-1]
		}
		k := q9(rng.q11(), c.b[s])
		if rng.q11() < c.m[s] {
			obs[t] = v2
		} else {
			obs[t] = k
		}
	}
	return obs
}

func q2(path string) ([]*t1, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	lines := strings.Split(string(raw), "\n")
	var cases []*t1
	i := 0
	skip := func() {
		for i < len(lines) {
			s := strings.TrimSpace(lines[i])
			if s == "" || strings.HasPrefix(s, "#") {
				i++
				continue
			}
			return
		}
	}
	for {
		skip()
		if i >= len(lines) {
			break
		}
		line := strings.TrimSpace(lines[i])
		if !strings.HasPrefix(line, "CASE") {
			return nil, fmt.Errorf("expected CASE, got %q", line)
		}
		c := &t1{id: strings.TrimSpace(strings.TrimPrefix(line, "CASE"))}
		i++
		skip()
		var tagN, tagK, tagT, tagD string
		if _, err := fmt.Sscan(lines[i], &tagN, &c.n, &tagK, &c.k, &tagT,
			&c.t, &tagD, &c.dmax); err != nil {
			return nil, fmt.Errorf("bad dims line %q: %v", lines[i], err)
		}
		i++
		skip()
		var tagS string
		if _, err := fmt.Sscan(lines[i], &tagS, &c.seed); err != nil ||
			tagS != "SEED" {
			return nil, fmt.Errorf("bad SEED line %q", lines[i])
		}
		i++
		q6 := func(prefix string, want int) ([]float64, error) {
			skip()
			toks := strings.Fields(lines[i])
			if len(toks) != want+1 || toks[0] != prefix {
				return nil, fmt.Errorf("expected %s row with %d values, got %q",
					prefix, want, lines[i])
			}
			row := make([]float64, want)
			for j, tk := range toks[1:] {
				v, err := strconv.ParseFloat(tk, 64)
				if err != nil {
					return nil, err
				}
				row[j] = v
			}
			i++
			return row, nil
		}
		var err error
		if c.pi, err = q6("PI", c.n); err != nil {
			return nil, err
		}
		for r := 0; r < c.n; r++ {
			row, err := q6("A", c.n)
			if err != nil {
				return nil, err
			}
			c.a = append(c.a, row)
		}
		for r := 0; r < c.n; r++ {
			row, err := q6("B", c.k)
			if err != nil {
				return nil, err
			}
			c.b = append(c.b, row)
		}
		for r := 0; r < c.n; r++ {
			row, err := q6("D", c.dmax)
			if err != nil {
				return nil, err
			}
			c.d = append(c.d, row)
		}
		if c.m, err = q6("M", c.n); err != nil {
			return nil, err
		}
		skip()
		if strings.TrimSpace(lines[i]) != "END" {
			return nil, fmt.Errorf("expected END for %s, got %q", c.id, lines[i])
		}
		i++
		cases = append(cases, c)
	}
	return cases, nil
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: ref <input_file> <output_file>")
		os.Exit(2)
	}
	inPath := os.Args[1]
	outPath := os.Args[2]
	cases, err := q2(inPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, "parse error:", err)
		os.Exit(1)
	}
	if len(cases) > 200 {
		fmt.Fprintln(os.Stderr, "probe limit: at most 200 cases per file")
		os.Exit(2)
	}
	for _, c := range cases {
		if c.t > 128 {
			fmt.Fprintf(os.Stderr, "probe limit: case %s has T=%d, the reference only runs cases with T <= 128\n", c.id, c.t)
			os.Exit(2)
		}
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	f, err := os.Create(outPath)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	w := bufio.NewWriter(f)
	for _, c := range cases {
		obs := q8(c)
		m := q1(c)
		loglik, _, nseg := m.q7(obs)
		fmt.Fprintf(w, "CASE %s\n", c.id)
		w.WriteString("O")
		for _, o := range obs {
			if o == v2 {
				w.WriteString(" ?")
			} else {
				fmt.Fprintf(w, " %d", o)
			}
		}
		w.WriteString("\n")
		fmt.Fprintf(w, "LOGLIK %.17g\n", loglik)
		fmt.Fprintf(w, "NSEG %.17g\n", nseg)
		w.WriteString("END\n")
	}
	if err := w.Flush(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := f.Close(); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
