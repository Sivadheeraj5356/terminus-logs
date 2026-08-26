package layercore

type FamilySpec struct {
	Tag       uint32
	DiagScale float64
}

type OperatorBlock struct {
	scale float64
}

func (f FamilySpec) Block() OperatorBlock {
	return OperatorBlock{scale: f.DiagScale}
}

func (o OperatorBlock) Apply(v [4]float64) [4]float64 {
	var out [4]float64
	for i := 0; i < 4; i++ {
		out[i] = v[i] * o.scale
	}
	return out
}
