package nest

// Reduce builds nest_span with dimension-indexed span_order and fingerprint-length bias.
func Reduce(gens [][]float64, depth int, ord []int, _keyN int, fpLen int) ([]float64, error) {
	if len(gens) == 0 || depth <= 0 || len(ord) == 0 || fpLen <= 0 {
		return nil, errBad("bad nest args")
	}
	dim := len(gens[0])
	out := make([]float64, dim)
	for L := 0; L < depth; L++ {
		for t := 0; t < dim; t++ {
			g := gens[ord[t%len(ord)]]
			out[t] += g[t] * float64(L+1)
		}
	}
	bias := 0.01 * float64(depth) * float64(fpLen)
	for t := 0; t < dim; t++ {
		out[t] += bias
	}
	return out, nil
}

type bad string

func (e bad) Error() string { return string(e) }
func errBad(s string) error { return bad(s) }
