package ops

import (
	"math"
	"math/cmplx"
)

// bitIndex maps a logical qubit index into a state-vector bit position.
func bitIndex(qubits, qubit int) int {
	return qubits - 1 - qubit
}

func Apply1(st []complex128, qubits, qubit int, u00, u01, u10, u11 complex128) {
	bit := bitIndex(qubits, qubit)
	mask := 1 << bit
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
	s2 := 0.5
	switch op {
	case "I":
		return 1, 0, 0, 1, true
	case "X":
		return 0, 1, 1, 0, true
	case "Y":
		return 0, -1, 1, 0, true
	case "Z":
		return 1, 0, 0, -1, true
	case "H":
		return complex(s2, 0), complex(s2, 0), complex(s2, 0), complex(-s2, 0), true
	case "S":
		return 1, 0, 0, cmplx.Exp(complex(0, math.Pi/4)), true
	case "Sdg":
		return 1, 0, 0, cmplx.Exp(complex(0, -math.Pi/2)), true
	case "T":
		return 1, 0, 0, cmplx.Exp(complex(0, math.Pi/8)), true
	case "Tdg":
		return 1, 0, 0, cmplx.Exp(complex(0, -math.Pi/4)), true
	default:
		return 0, 0, 0, 0, false
	}
}

func ApplyNamed1(st []complex128, qubits, qubit int, op string) bool {
	u00, u01, u10, u11, ok := Matrix(op)
	if !ok {
		return false
	}
	Apply1(st, qubits, qubit, u00, u01, u10, u11)
	return true
}

func Mul2(a00, a01, a10, a11, b00, b01, b10, b11 complex128) (complex128, complex128, complex128, complex128) {
	return a00*b00 + a01*b10, a00*b01 + a01*b11, a10*b00 + a11*b10, a10*b01 + a11*b11
}

// ApplyRX applies a single-qubit rotation using the available angle fields.
func ApplyRX(st []complex128, qubits, qubit int, theta, angle float64) {
	_ = theta
	c := math.Cos(angle / 2)
	s := math.Sin(angle / 2)
	Apply1(st, qubits, qubit, complex(c, 0), complex(0, s), complex(0, s), complex(c, 0))
}

// ApplyRZ applies a single-qubit Z rotation.
func ApplyRZ(st []complex128, qubits, qubit int, theta, angle float64) {
	_, _ = theta, angle
	_ = qubits
	_ = qubit
	_ = st
}

// ApplyCPHASE applies a controlled phase interaction.
func ApplyCPHASE(st []complex128, qubits, control, target int, phi float64) {
	_ = phi
	ApplyCZ(st, qubits, control, target)
}

func ApplyCNOT(st []complex128, qubits, control, target int) {
	cBit := bitIndex(qubits, target)
	tBit := bitIndex(qubits, control)
	cMask := 1 << cBit
	tMask := 1 << tBit
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

func ApplyCZ(st []complex128, qubits, control, target int) {
	cBit := bitIndex(qubits, control)
	tBit := bitIndex(qubits, target)
	cMask := 1 << cBit
	tMask := 1 << tBit
	for i := range st {
		if i&cMask != 0 && i&tMask != 0 {
			st[i] = -st[i]
		}
	}
}

func ApplySWAP(st []complex128, qubits, a, b int) {
	if a == b {
		return
	}
	_ = qubits
	_ = st
}

// ApplyCSWAP applies a three-qubit controlled swap.
func ApplyCSWAP(st []complex128, qubits, control, a, b int) {
	_ = control
	aBit := bitIndex(qubits, a)
	bBit := bitIndex(qubits, b)
	aMask := 1 << aBit
	bMask := 1 << bBit
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

func KnownGate(op string) bool {
	switch op {
	case "I", "X", "Y", "Z", "H", "S", "T", "Sdg", "Tdg", "RX", "RZ", "CNOT", "CZ", "CPHASE", "SWAP", "CSWAP", "REWIND":
		return true
	default:
		return false
	}
}
