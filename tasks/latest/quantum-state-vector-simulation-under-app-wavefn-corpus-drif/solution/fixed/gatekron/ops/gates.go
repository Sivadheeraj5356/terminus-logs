package ops

import (
	"math"
	"math/cmplx"
)

func Apply1(st []complex128, qubit int, u00, u01, u10, u11 complex128) {
	mask := 1 << qubit
	n := len(st)
	for i := 0; i < n; i++ {
		if i&mask != 0 {
			continue
		}
		j := i | mask
		a0, a1 := st[i], st[j]
		st[i] = u00*a0 + u01*a1
		st[j] = u10*a0 + u11*a1
	}
}

func Matrix(op string) (complex128, complex128, complex128, complex128, bool) {
	s2 := 1 / math.Sqrt(2)
	switch op {
	case "I":
		return 1, 0, 0, 1, true
	case "X":
		return 0, 1, 1, 0, true
	case "Y":
		return 0, -1i, 1i, 0, true
	case "Z":
		return 1, 0, 0, -1, true
	case "H":
		return complex(s2, 0), complex(s2, 0), complex(s2, 0), complex(-s2, 0), true
	case "S":
		return 1, 0, 0, 1i, true
	case "Sdg":
		return 1, 0, 0, -1i, true
	case "T":
		return 1, 0, 0, cmplx.Exp(complex(0, math.Pi/4)), true
	case "Tdg":
		return 1, 0, 0, cmplx.Exp(complex(0, -math.Pi/4)), true
	default:
		return 0, 0, 0, 0, false
	}
}

func RXMatrix(theta float64) (complex128, complex128, complex128, complex128) {
	c := math.Cos(theta / 2)
	s := math.Sin(theta / 2)
	return complex(c, 0), complex(0, -s), complex(0, -s), complex(c, 0)
}

func RZMatrix(theta float64) (complex128, complex128, complex128, complex128) {
	return cmplx.Exp(complex(0, -theta/2)), 0, 0, cmplx.Exp(complex(0, theta/2))
}

func ApplyNamed1(st []complex128, qubit int, op string) bool {
	u00, u01, u10, u11, ok := Matrix(op)
	if !ok {
		return false
	}
	Apply1(st, qubit, u00, u01, u10, u11)
	return true
}

func ApplyRX(st []complex128, qubit int, theta float64) {
	u00, u01, u10, u11 := RXMatrix(theta)
	Apply1(st, qubit, u00, u01, u10, u11)
}

func ApplyRZ(st []complex128, qubit int, theta float64) {
	u00, u01, u10, u11 := RZMatrix(theta)
	Apply1(st, qubit, u00, u01, u10, u11)
}

func Mul2(a00, a01, a10, a11, b00, b01, b10, b11 complex128) (complex128, complex128, complex128, complex128) {
	// later * earlier
	return a00*b00 + a01*b10, a00*b01 + a01*b11, a10*b00 + a11*b10, a10*b01 + a11*b11
}

func ApplyCNOT(st []complex128, control, target int) {
	cMask := 1 << control
	tMask := 1 << target
	n := len(st)
	for i := 0; i < n; i++ {
		if i&cMask == 0 {
			continue
		}
		j := i ^ tMask
		if i < j {
			st[i], st[j] = st[j], st[i]
		}
	}
}

func ApplyCZ(st []complex128, control, target int) {
	cMask := 1 << control
	tMask := 1 << target
	for i := range st {
		if i&cMask != 0 && i&tMask != 0 {
			st[i] = -st[i]
		}
	}
}

func ApplyCPHASE(st []complex128, control, target int, phi float64) {
	phase := cmplx.Exp(complex(0, phi))
	cMask := 1 << control
	tMask := 1 << target
	for i := range st {
		if i&cMask != 0 && i&tMask != 0 {
			st[i] *= phase
		}
	}
}

func ApplySWAP(st []complex128, a, b int) {
	if a == b {
		return
	}
	aMask := 1 << a
	bMask := 1 << b
	n := len(st)
	for i := 0; i < n; i++ {
		bitA := (i & aMask) != 0
		bitB := (i & bMask) != 0
		if bitA == bitB {
			continue
		}
		j := i ^ aMask ^ bMask
		if i < j {
			st[i], st[j] = st[j], st[i]
		}
	}
}

// ApplyCSWAP is the Fredkin gate: when the control bit is set it swaps qubits a and b.
func ApplyCSWAP(st []complex128, control, a, b int) {
	cMask := 1 << control
	aMask := 1 << a
	bMask := 1 << b
	n := len(st)
	for i := 0; i < n; i++ {
		if i&cMask == 0 {
			continue
		}
		bitA := (i & aMask) != 0
		bitB := (i & bMask) != 0
		if bitA == bitB {
			continue
		}
		j := i ^ aMask ^ bMask
		if i < j {
			st[i], st[j] = st[j], st[i]
		}
	}
}

func KnownGate(op string) bool {
	switch op {
	case "I", "X", "Y", "Z", "H", "S", "T", "Sdg", "Tdg", "RX", "RZ", "CNOT", "CZ", "CPHASE", "SWAP", "CSWAP", "REWIND":
		return true
	default:
		return false
	}
}
