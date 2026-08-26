package vector

import (
	"fmt"
	"math"
	"math/cmplx"
)

// FormatAmp renders one amplitude as real and imaginary decimal strings.
func FormatAmp(z complex128) (string, string) {
	return fmt.Sprintf("%.6f", real(z)), fmt.Sprintf("%.6f", imag(z))
}

func FormatMetric(v float64) string {
	return fmt.Sprintf("%.6f", v)
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
