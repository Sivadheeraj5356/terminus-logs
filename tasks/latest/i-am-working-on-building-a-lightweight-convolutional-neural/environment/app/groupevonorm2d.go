package main

type GroupEvoNorm2D struct {
	NumGroups  int
	Channels   int
	Gammas     []float64
	Betas      []float64
	V          []float64
	GammaGrad  []float64
	BetaGrad   []float64
	VGrad      []float64
	Input      *Tensor
	Normalized *Tensor
}

func NewGroupEvoNorm2D(channels, numGroups int) *GroupEvoNorm2D {
	gn := &GroupEvoNorm2D{
		NumGroups: numGroups,
		Channels:  channels,
		Gammas:    make([]float64, channels),
		Betas:     make([]float64, channels),
		V:         make([]float64, channels),
		GammaGrad: make([]float64, channels),
		BetaGrad:  make([]float64, channels),
		VGrad:     make([]float64, channels),
	}
	for i := 0; i < channels; i++ {
		gn.Gammas[i] = 1.0
		gn.V[i] = 1.0
	}
	return gn
}

func (gn *GroupEvoNorm2D) Forward(input *Tensor) *Tensor {
	panic("not implemented")
}

func (gn *GroupEvoNorm2D) Backward(outputGrad *Tensor) *Tensor {
	panic("not implemented")
}

func (gn *GroupEvoNorm2D) Update(lr float64) {
	panic("not implemented")
}
