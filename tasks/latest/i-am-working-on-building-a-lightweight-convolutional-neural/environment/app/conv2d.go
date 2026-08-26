package main

type DeformableConv2D struct {
	InChannels    int
	OutChannels   int
	KernelSize    int
	Stride        int
	Padding       int
	InH           int
	InW           int
	OutH          int
	OutW          int
	Groups        int
	Weights       []float64
	Biases        []float64
	OffsetWeights []float64
	OffsetBiases  []float64
	WeightGrad    []float64
	BiasGrad      []float64
	OffsetWGrad   []float64
	OffsetBGrad   []float64
	SplineAlpha   []float64
	SplineAlphaGrad []float64
	U             []float64
	V             []float64
	Input         *Tensor
	tildeW        []float64
	sigma         []float64
	hatW          []float64
	mu            []float64
	varVal        []float64
	bjorckW       [][]float64
	Training      bool
	Offsets       []float64
	Masks         []float64
}

func NewDeformableConv2D(inChannels, outChannels, kernelSize, stride, padding, inH, inW, groups int) *DeformableConv2D {
	outH := (inH - kernelSize + 2*padding)/stride + 1
	outW := (inW - kernelSize + 2*padding)/stride + 1
	cOff := 3 * kernelSize * kernelSize
	return &DeformableConv2D{
		InChannels:    inChannels,
		OutChannels:   outChannels,
		KernelSize:    kernelSize,
		Stride:        stride,
		Padding:       padding,
		InH:           inH,
		InW:           inW,
		OutH:          outH,
		OutW:          outW,
		Groups:        groups,
		Weights:       make([]float64, outChannels*(inChannels/groups)*kernelSize*kernelSize),
		Biases:        make([]float64, outChannels),
		OffsetWeights: make([]float64, cOff*inChannels*kernelSize*kernelSize),
		OffsetBiases:  make([]float64, cOff),
		WeightGrad:    make([]float64, outChannels*(inChannels/groups)*kernelSize*kernelSize),
		BiasGrad:      make([]float64, outChannels),
		OffsetWGrad:   make([]float64, cOff*inChannels*kernelSize*kernelSize),
		OffsetBGrad:   make([]float64, cOff),
		SplineAlpha:   make([]float64, inChannels),
		SplineAlphaGrad: make([]float64, inChannels),
		Training:      true,
		Offsets:       make([]float64, 2*kernelSize*kernelSize*outH*outW),
		Masks:         make([]float64, kernelSize*kernelSize*outH*outW),
	}
	for i := 0; i < inChannels; i++ {
		c.SplineAlpha[i] = -0.5
	}
	return c

func (c *DeformableConv2D) Forward(input *Tensor) *Tensor {
	panic("not implemented")
}

func (c *DeformableConv2D) Backward(outputGrad *Tensor) *Tensor {
	panic("not implemented")
}

func (c *DeformableConv2D) Update(lr float64) {
	panic("not implemented")
}
