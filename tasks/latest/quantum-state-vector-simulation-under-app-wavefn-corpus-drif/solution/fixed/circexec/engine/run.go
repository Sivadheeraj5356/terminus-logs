package engine

import (
	"encoding/json"
	"math/cmplx"
	"os"
	"sort"

	"qstatebench/ampstore/vector"
	"qstatebench/gatekron/ops"
	"qstatebench/numpolicy/tol"
)

type Gate struct {
	Op        string   `json:"op"`
	Qubit     *int     `json:"qubit"`
	Control   *int     `json:"control"`
	Target    *int     `json:"target"`
	A         *int     `json:"a"`
	B         *int     `json:"b"`
	Theta     *float64 `json:"theta"`
	Phi       *float64 `json:"phi"`
	Angle     *float64 `json:"angle"`
	Depth     *float64 `json:"depth"`
	BlockFuse *bool    `json:"block_fuse"`
}

type Circuit struct {
	CircuitID       string                 `json:"circuit_id"`
	Qubits          int                    `json:"qubits"`
	Gates           []Gate                 `json:"gates"`
	NormEps         *float64               `json:"norm_eps"`
	FidelityEps     *float64               `json:"fidelity_eps"`
	FuseAdjacent    *bool                  `json:"fuse_adjacent"`
	CheckUnitary    *bool                  `json:"check_unitary"`
	GhostEps        *float64               `json:"ghost_eps"`
	PolicyOverrides map[string]interface{} `json:"policy_overrides"`
}

type AmpOut struct {
	Re string `json:"re"`
	Im string `json:"im"`
}

type Anomaly struct {
	Kind      string `json:"kind"`
	GateIndex int    `json:"gate_index"`
	Detail    string `json:"detail"`
}

type CircuitOut struct {
	CircuitID       string    `json:"circuit_id"`
	Qubits          int       `json:"qubits"`
	Status          string    `json:"status"`
	GateCount       int       `json:"gate_count"`
	FusedPairs      int       `json:"fused_pairs"`
	Norm            string    `json:"norm"`
	ReverseFidelity string    `json:"reverse_fidelity"`
	Amplitudes      []AmpOut  `json:"amplitudes"`
	Anomalies       []Anomaly `json:"anomalies"`
}

type Report struct {
	Circuits []CircuitOut `json:"circuits"`
}

func LoadCircuit(path string) (Circuit, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return Circuit{}, err
	}
	var sc Circuit
	if err := json.Unmarshal(data, &sc); err != nil {
		return Circuit{}, err
	}
	return sc, nil
}

func qubitOf(g Gate) (int, bool) {
	if g.Qubit == nil {
		return 0, false
	}
	return *g.Qubit, true
}

func isFusable(op string) bool {
	switch op {
	case "I", "X", "Y", "Z", "H", "S", "T", "Sdg", "Tdg":
		return true
	default:
		return false
	}
}

func blockFuse(g Gate) bool {
	return g.BlockFuse != nil && *g.BlockFuse
}

// histEntry records one effective (post-fusion) step actually applied to the
// live state so its inverse can be replayed by REWIND and reverse fidelity.
type histEntry struct {
	kind                   string // one, cnot, cz, swap, cphase, cswap
	qubit                  int
	m00, m01, m10, m11     complex128
	control, target, a, b  int
	phi                    float64
}

func (h histEntry) applyInverse(st []complex128) {
	switch h.kind {
	case "one":
		ops.Apply1(st, h.qubit, cmplx.Conj(h.m00), cmplx.Conj(h.m10), cmplx.Conj(h.m01), cmplx.Conj(h.m11))
	case "cnot":
		ops.ApplyCNOT(st, h.control, h.target)
	case "cz":
		ops.ApplyCZ(st, h.control, h.target)
	case "swap":
		ops.ApplySWAP(st, h.a, h.b)
	case "cphase":
		ops.ApplyCPHASE(st, h.control, h.target, -h.phi)
	case "cswap":
		ops.ApplyCSWAP(st, h.control, h.a, h.b)
	}
}

type step struct {
	op                 string
	qubit              int
	control            int
	target             int
	a                  int
	b                  int
	theta              float64
	phi                float64
	depth              float64
	gateIndex          int
	useMat             bool
	hasTheta           bool
	hasDepth           bool
	m00, m01, m10, m11 complex128
}

func gateToStep(g Gate, idx int) step {
	st := step{op: g.Op, gateIndex: idx}
	if g.Qubit != nil {
		st.qubit = *g.Qubit
	}
	if g.Control != nil {
		st.control = *g.Control
	}
	if g.Target != nil {
		st.target = *g.Target
	}
	if g.A != nil {
		st.a = *g.A
	}
	if g.B != nil {
		st.b = *g.B
	}
	if g.Theta != nil {
		st.theta = *g.Theta
		st.hasTheta = true
	}
	if g.Phi != nil {
		st.phi = *g.Phi
	}
	if g.Depth != nil {
		st.depth = *g.Depth
		st.hasDepth = true
	}
	return st
}

func fuseSteps(gates []Gate, enabled bool) ([]step, int, []Anomaly) {
	steps := make([]step, 0, len(gates))
	skips := make([]Anomaly, 0)
	fusedPairs := 0
	i := 0
	for i < len(gates) {
		g := gates[i]
		if enabled && isFusable(g.Op) {
			q, ok := qubitOf(g)
			if ok && i+1 < len(gates) {
				g2 := gates[i+1]
				q2, ok2 := qubitOf(g2)
				if ok2 && q == q2 && g.Op == g2.Op && isFusable(g2.Op) {
					if blockFuse(g) {
						skips = append(skips, Anomaly{
							Kind: "FUSION_SKIP", GateIndex: i, Detail: g.Op,
						})
						steps = append(steps, gateToStep(g, i))
						steps = append(steps, gateToStep(g2, i+1))
						i += 2
						continue
					}
					u00, u01, u10, u11, okA := ops.Matrix(g.Op)
					v00, v01, v10, v11, okB := ops.Matrix(g2.Op)
					if okA && okB {
						m00, m01, m10, m11 := ops.Mul2(v00, v01, v10, v11, u00, u01, u10, u11)
						steps = append(steps, step{
							op:        g.Op,
							qubit:     q,
							gateIndex: i,
							useMat:    true,
							m00:       m00,
							m01:       m01,
							m10:       m10,
							m11:       m11,
						})
						fusedPairs++
						i += 2
						continue
					}
				}
			}
		}
		steps = append(steps, gateToStep(g, i))
		i++
	}
	return steps, fusedPairs, skips
}

func oor(q, qubits int) bool {
	return q < 0 || q >= qubits
}

// applyStep applies one non-REWIND effective step. It returns an anomaly kind and
// detail (empty when successful), the history entry to record, and whether that
// entry should be pushed.
func applyStep(st []complex128, qubits int, s step) (string, string, histEntry, bool) {
	switch s.op {
	case "CNOT":
		if s.control == s.target || oor(s.control, qubits) || oor(s.target, qubits) {
			return "QUBIT_OUT_OF_RANGE", "cnot", histEntry{}, false
		}
		ops.ApplyCNOT(st, s.control, s.target)
		return "", "", histEntry{kind: "cnot", control: s.control, target: s.target}, true
	case "CZ":
		if s.control == s.target || oor(s.control, qubits) || oor(s.target, qubits) {
			return "QUBIT_OUT_OF_RANGE", "cz", histEntry{}, false
		}
		ops.ApplyCZ(st, s.control, s.target)
		return "", "", histEntry{kind: "cz", control: s.control, target: s.target}, true
	case "CPHASE":
		if s.control == s.target || oor(s.control, qubits) || oor(s.target, qubits) {
			return "QUBIT_OUT_OF_RANGE", "cphase", histEntry{}, false
		}
		ops.ApplyCPHASE(st, s.control, s.target, s.phi)
		return "", "", histEntry{kind: "cphase", control: s.control, target: s.target, phi: s.phi}, true
	case "SWAP":
		if s.a == s.b || oor(s.a, qubits) || oor(s.b, qubits) {
			return "QUBIT_OUT_OF_RANGE", "swap", histEntry{}, false
		}
		ops.ApplySWAP(st, s.a, s.b)
		return "", "", histEntry{kind: "swap", a: s.a, b: s.b}, true
	case "CSWAP":
		if s.control == s.a || s.control == s.b || s.a == s.b ||
			oor(s.control, qubits) || oor(s.a, qubits) || oor(s.b, qubits) {
			return "QUBIT_OUT_OF_RANGE", "cswap", histEntry{}, false
		}
		ops.ApplyCSWAP(st, s.control, s.a, s.b)
		return "", "", histEntry{kind: "cswap", control: s.control, a: s.a, b: s.b}, true
	case "RX":
		if !s.hasTheta {
			return "UNKNOWN_GATE", "RX", histEntry{}, false
		}
		if oor(s.qubit, qubits) {
			return "QUBIT_OUT_OF_RANGE", "RX", histEntry{}, false
		}
		m00, m01, m10, m11 := ops.RXMatrix(s.theta)
		ops.Apply1(st, s.qubit, m00, m01, m10, m11)
		return "", "", histEntry{kind: "one", qubit: s.qubit, m00: m00, m01: m01, m10: m10, m11: m11}, true
	case "RZ":
		if !s.hasTheta {
			return "UNKNOWN_GATE", "RZ", histEntry{}, false
		}
		if oor(s.qubit, qubits) {
			return "QUBIT_OUT_OF_RANGE", "RZ", histEntry{}, false
		}
		m00, m01, m10, m11 := ops.RZMatrix(s.theta)
		ops.Apply1(st, s.qubit, m00, m01, m10, m11)
		return "", "", histEntry{kind: "one", qubit: s.qubit, m00: m00, m01: m01, m10: m10, m11: m11}, true
	default:
		if !ops.KnownGate(s.op) && !s.useMat {
			return "UNKNOWN_GATE", s.op, histEntry{}, false
		}
		if oor(s.qubit, qubits) {
			return "QUBIT_OUT_OF_RANGE", s.op, histEntry{}, false
		}
		if s.useMat {
			ops.Apply1(st, s.qubit, s.m00, s.m01, s.m10, s.m11)
			return "", "", histEntry{kind: "one", qubit: s.qubit, m00: s.m00, m01: s.m01, m10: s.m10, m11: s.m11}, true
		}
		m00, m01, m10, m11, ok := ops.Matrix(s.op)
		if !ok {
			return "UNKNOWN_GATE", s.op, histEntry{}, false
		}
		ops.Apply1(st, s.qubit, m00, m01, m10, m11)
		return "", "", histEntry{kind: "one", qubit: s.qubit, m00: m00, m01: m01, m10: m10, m11: m11}, true
	}
}

func Simulate(sc Circuit) CircuitOut {
	normEps := 1e-9
	if sc.NormEps != nil {
		normEps = *sc.NormEps
	}
	fidEps := 1e-9
	if sc.FidelityEps != nil {
		fidEps = *sc.FidelityEps
	}
	fuseAdj := true
	if sc.FuseAdjacent != nil {
		fuseAdj = *sc.FuseAdjacent
	}
	checkU := true
	if sc.CheckUnitary != nil {
		checkU = *sc.CheckUnitary
	}
	ghostEps := 0.0
	if sc.GhostEps != nil {
		ghostEps = *sc.GhostEps
	}
	normEps, fidEps, fuseAdj, checkU, ghostEps = tol.ResolveCircuit(
		normEps, fidEps, fuseAdj, checkU, ghostEps, sc.PolicyOverrides,
	)

	st := vector.ZeroState(sc.Qubits)
	steps, fusedPairs, skipAnoms := fuseSteps(sc.Gates, fuseAdj)
	anomalies := make([]Anomaly, 0, len(skipAnoms))
	anomalies = append(anomalies, skipAnoms...)

	history := make([]histEntry, 0, len(steps))
	structuralStop := false
	for _, s := range steps {
		if s.op == "REWIND" {
			if !s.hasDepth || s.depth < 0 {
				anomalies = append(anomalies, Anomaly{Kind: "UNKNOWN_GATE", GateIndex: s.gateIndex, Detail: "REWIND"})
				structuralStop = true
				break
			}
			d := int(s.depth)
			if d == 0 {
				continue
			}
			if d > len(history) {
				anomalies = append(anomalies, Anomaly{Kind: "REWIND_OVERFLOW", GateIndex: s.gateIndex, Detail: "overflow"})
				structuralStop = true
				break
			}
			for k := 0; k < d; k++ {
				e := history[len(history)-1]
				history = history[:len(history)-1]
				e.applyInverse(st)
			}
			continue
		}
		kind, detail, entry, pushed := applyStep(st, sc.Qubits, s)
		if kind != "" {
			anomalies = append(anomalies, Anomaly{Kind: kind, GateIndex: s.gateIndex, Detail: detail})
			structuralStop = true
			break
		}
		if pushed {
			history = append(history, entry)
		}
	}

	revClone := vector.Clone(st)
	vector.GhostPrune(st, ghostEps)
	norm := vector.Norm(st)
	revFid := 0.0
	if !structuralStop {
		for i := len(history) - 1; i >= 0; i-- {
			history[i].applyInverse(revClone)
		}
		revFid = vector.FidelityZero(revClone)
		if tol.NormDrifted(norm, normEps) {
			anomalies = append(anomalies, Anomaly{
				Kind: "NORM_DRIFT", GateIndex: -1, Detail: vector.FormatMetric(norm),
			})
		}
		if checkU && tol.FidelityDrifted(revFid, fidEps) {
			anomalies = append(anomalies, Anomaly{
				Kind: "UNITARY_DRIFT", GateIndex: -1, Detail: vector.FormatMetric(revFid),
			})
		}
	}
	vector.PhaseLock(st)

	amps := make([]AmpOut, len(st))
	for i, z := range st {
		re, im := vector.FormatAmp(z)
		amps[i] = AmpOut{Re: re, Im: im}
	}

	sort.Slice(anomalies, func(i, j int) bool {
		if anomalies[i].Kind != anomalies[j].Kind {
			return anomalies[i].Kind < anomalies[j].Kind
		}
		if anomalies[i].GateIndex != anomalies[j].GateIndex {
			return anomalies[i].GateIndex < anomalies[j].GateIndex
		}
		return anomalies[i].Detail < anomalies[j].Detail
	})

	status := "VALID"
	if len(anomalies) > 0 {
		status = "INVALID"
	}

	return CircuitOut{
		CircuitID:       sc.CircuitID,
		Qubits:          sc.Qubits,
		Status:          status,
		GateCount:       len(sc.Gates),
		FusedPairs:      fusedPairs,
		Norm:            vector.FormatMetric(norm),
		ReverseFidelity: vector.FormatMetric(revFid),
		Amplitudes:      amps,
		Anomalies:       anomalies,
	}
}
