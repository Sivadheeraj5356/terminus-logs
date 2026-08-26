package vector

import (
	"fmt"
	"math"
	"math/cmplx"
)

func FormatAmp(z complex128) (string, string) {
	r, i := real(z), imag(z)
	if r == 0 {
		r = 0
	}
	if i == 0 {
		i = 0
	}
	return fmt.Sprintf("%.10f", r), fmt.Sprintf("%.10f", i)
}

func FormatMetric(v float64) string {
	if v == 0 {
		v = 0
	}
	return fmt.Sprintf("%.10f", v)
}

func ZeroState(qubits int) []complex128 {
	n := 1 << qubits
	st := make([]complex128, n)
	st[0] = 1
	return st
}

func Norm(st []complex128) float64 {
	var s float64
	for _, a := range st {
		s += real(a * cmplx.Conj(a))
	}
	return math.Sqrt(s)
}

func FidelityZero(st []complex128) float64 {
	if len(st) == 0 {
		return 0
	}
	return real(st[0] * cmplx.Conj(st[0]))
}

func Clone(st []complex128) []complex128 {
	out := make([]complex128, len(st))
	copy(out, st)
	return out
}

// GhostPrune zeroes any amplitude whose modulus is strictly below eps and, if any
// previously non-zero amplitude was zeroed, renormalizes the state to unit norm.
// A non-positive eps leaves the state unchanged.
func GhostPrune(st []complex128, eps float64) {
	if eps <= 0 {
		return
	}
	zeroed := false
	for i, z := range st {
		if z != 0 && cmplx.Abs(z) < eps {
			st[i] = 0
			zeroed = true
		}
	}
	if !zeroed {
		return
	}
	var s float64
	for _, z := range st {
		s += real(z)*real(z) + imag(z)*imag(z)
	}
	n := math.Sqrt(s)
	if n > 0 {
		nn := complex(n, 0)
		for i := range st {
			st[i] /= nn
		}
	}
}

// PhaseLock multiplies the whole state by a global phase so that the first
// amplitude with modulus above 1e-15 becomes real and non-negative. If every
// amplitude is at or below 1e-15 the state is left unchanged.
func PhaseLock(st []complex128) {
	lead := -1
	for i, z := range st {
		if cmplx.Abs(z) > 1e-15 {
			lead = i
			break
		}
	}
	if lead < 0 {
		return
	}
	mag := cmplx.Abs(st[lead])
	factor := cmplx.Conj(st[lead]) / complex(mag, 0)
	for i := range st {
		st[i] *= factor
	}
}
