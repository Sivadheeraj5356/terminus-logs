package layercore

type MeshView struct {
	Rhs [4]float64
}

func CanonicalRhs() MeshView {
	return MeshView{Rhs: [4]float64{1.0, 0.1, 0.02, 0.0}}
}

func (m MeshView) ResidualNorm(op OperatorBlock, v [4]float64) float64 {
	out := op.Apply(v)
	var acc float64
	for i := 0; i < 4; i++ {
		d := out[i] - m.Rhs[i]
		acc += d * d
	}
	return acc
}
