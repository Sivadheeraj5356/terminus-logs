package nest

// Reduce builds the zonotope nest_span vector for graded lanes.
func Reduce(gens [][]float64, depth int, ord []int, keyN int, _fpLen int) ([]float64, error) {
	if len(gens) == 0 || depth <= 0 || len(ord) == 0 || keyN <= 0 {
		return nil, errBad("bad nest args")
	}
	dim := len(gens[0])
	out := make([]float64, dim)
	for L := 0; L < depth; L++ {
		g := gens[ord[L%len(ord)]]
		for t := 0; t < dim; t++ {
			out[t] += g[t] * float64(L+1)
		}
	}
	bias := 0.01 * float64(depth) * float64(keyN)
	for t := 0; t < dim; t++ {
		out[t] += bias
	}
	return out, nil
}

type bad string

func (e bad) Error() string { return string(e) }
func errBad(s string) error { return bad(s) }
