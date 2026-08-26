package engine

import (
	"encoding/json"
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

type step struct {
	op        string
	qubit     int
	control   int
	target    int
	a         int
	b         int
	theta     float64
	phi       float64
	angle     float64
	gateIndex int
	fused     bool
}

func fuseSteps(gates []Gate, enabled bool) ([]step, int) {
	steps := make([]step, 0, len(gates))
	fusedPairs := 0
	i := 0
	for i < len(gates) {
		g := gates[i]
		if enabled && isFusable(g.Op) {
			q, ok := qubitOf(g)
			if ok && i+1 < len(gates) {
				g2 := gates[i+1]
				q2, ok2 := qubitOf(g2)
				if ok2 && q == q2 && isFusable(g2.Op) {
					u00, u01, u10, u11, okA := ops.Matrix(g.Op)
					v00, v01, v10, v11, okB := ops.Matrix(g2.Op)
					if okA && okB {
						m00, m01, m10, m11 := ops.Mul2(u00, u01, u10, u11, v00, v01, v10, v11)
						steps = append(steps, step{
							op:        "__MAT__",
							qubit:     q,
							gateIndex: i,
							fused:     true,
						})
						_ = m00
						_ = m01
						_ = m10
						_ = m11
						steps[len(steps)-1].op = g2.Op
						fusedPairs++
						i += 2
						continue
					}
				}
			}
		}
		st := step{op: g.Op, gateIndex: i}
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
		}
		if g.Phi != nil {
			st.phi = *g.Phi
		}
		if g.Angle != nil {
			st.angle = *g.Angle
		}
		steps = append(steps, st)
		i++
	}
	return steps, fusedPairs
}

func applyStep(st []complex128, qubits int, s step) (string, string) {
	switch s.op {
	case "CNOT":
		if s.control < 0 || s.control >= qubits || s.target < 0 || s.target >= qubits {
			return "QUBIT_OUT_OF_RANGE", "cnot"
		}
		ops.ApplyCNOT(st, qubits, s.control, s.target)
		return "", ""
	case "CZ":
		if s.control < 0 || s.control >= qubits || s.target < 0 || s.target >= qubits {
			return "QUBIT_OUT_OF_RANGE", "cz"
		}
		ops.ApplyCZ(st, qubits, s.control, s.target)
		return "", ""
	case "CPHASE":
		if s.control < 0 || s.control >= qubits || s.target < 0 || s.target >= qubits {
			return "QUBIT_OUT_OF_RANGE", "cphase"
		}
		ops.ApplyCPHASE(st, qubits, s.control, s.target, s.phi)
		return "", ""
	case "SWAP":
		if s.a < 0 || s.a >= qubits || s.b < 0 || s.b >= qubits {
			return "QUBIT_OUT_OF_RANGE", "swap"
		}
		ops.ApplySWAP(st, qubits, s.a, s.b)
		return "", ""
	case "CSWAP":
		if s.control < 0 || s.control >= qubits || s.a < 0 || s.a >= qubits || s.b < 0 || s.b >= qubits {
			return "QUBIT_OUT_OF_RANGE", "cswap"
		}
		ops.ApplyCSWAP(st, qubits, s.control, s.a, s.b)
		return "", ""
	case "REWIND":
		return "", ""
	case "RX":
		if s.qubit < 0 || s.qubit >= qubits {
			return "QUBIT_OUT_OF_RANGE", "RX"
		}
		ops.ApplyRX(st, qubits, s.qubit, s.theta, s.angle)
		return "", ""
	case "RZ":
		if s.qubit < 0 || s.qubit >= qubits {
			return "QUBIT_OUT_OF_RANGE", "RZ"
		}
		ops.ApplyRZ(st, qubits, s.qubit, s.theta, s.angle)
		return "", ""
	default:
		if s.qubit < 0 || s.qubit >= qubits {
			return "QUBIT_OUT_OF_RANGE", s.op
		}
		if !isFusable(s.op) && s.op != "__MAT__" {
			_, _, _, _, ok := ops.Matrix(s.op)
			if !ok {
				return "UNKNOWN_GATE", s.op
			}
		}
		if !ops.ApplyNamed1(st, qubits, s.qubit, s.op) {
			return "UNKNOWN_GATE", s.op
		}
		return "", ""
	}
}

func inverseOp(op string) string {
	switch op {
	case "S":
		return "Sdg"
	case "T":
		return "Tdg"
	case "Sdg":
		return "S"
	case "Tdg":
		return "T"
	default:
		return op
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
	normEps, fidEps, fuseAdj, checkU = tol.ResolveCircuit(
		normEps, fidEps, fuseAdj, checkU, sc.PolicyOverrides,
	)

	st := vector.ZeroState(sc.Qubits)
	steps, fusedPairs := fuseSteps(sc.Gates, fuseAdj)
	anomalies := make([]Anomaly, 0)

	for _, s := range steps {
		kind, detail := applyStep(st, sc.Qubits, s)
		if kind != "" {
			anomalies = append(anomalies, Anomaly{Kind: kind, GateIndex: s.gateIndex, Detail: detail})
			break
		}
	}

	norm := vector.Norm(st)
	revFid := 0.0
	if len(anomalies) == 0 {
		rev := vector.Clone(st)
		for i := len(sc.Gates) - 1; i >= 0; i-- {
			g := sc.Gates[i]
			inv := Gate{
				Op:      inverseOp(g.Op),
				Qubit:   g.Qubit,
				Control: g.Control,
				Target:  g.Target,
				A:       g.A,
				B:       g.B,
				Theta:   g.Theta,
				Phi:     g.Phi,
				Angle:   g.Angle,
			}
			s := step{op: inv.Op, gateIndex: i}
			if inv.Qubit != nil {
				s.qubit = *inv.Qubit
			}
			if inv.Control != nil {
				s.control = *inv.Control
			}
			if inv.Target != nil {
				s.target = *inv.Target
			}
			if inv.A != nil {
				s.a = *inv.A
			}
			if inv.B != nil {
				s.b = *inv.B
			}
			if inv.Theta != nil {
				s.theta = *inv.Theta
			}
			if inv.Phi != nil {
				s.phi = *inv.Phi
			}
			if inv.Angle != nil {
				s.angle = *inv.Angle
			}
			applyStep(rev, sc.Qubits, s)
		}
		revFid = vector.FidelityZero(rev)
		if tol.NormDrifted(norm, normEps) {
			anomalies = append(anomalies, Anomaly{Kind: "NORM_DRIFT", GateIndex: -1, Detail: vector.FormatMetric(norm)})
		}
		if checkU && tol.FidelityDrifted(revFid, fidEps) {
			anomalies = append(anomalies, Anomaly{Kind: "UNITARY_DRIFT", GateIndex: -1, Detail: vector.FormatMetric(revFid)})
		}
	} else {
		revFid = vector.FidelityZero(st)
	}

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
