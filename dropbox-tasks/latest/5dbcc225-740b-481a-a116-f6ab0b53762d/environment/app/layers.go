package main

type Layer interface {
	Forward(input *Tensor) *Tensor
	Backward(outputGrad *Tensor) *Tensor
	Update(lr float64)
}

type ReLU struct {
	Input *Tensor
}

func NewReLU() *ReLU {
	return &ReLU{}
}

func (r *ReLU) Forward(input *Tensor) *Tensor {
	r.Input = input.Clone()
	out := NewTensor(input.Shape[0], input.Shape[1], input.Shape[2])
	for i, val := range input.Data {
		if val > 0 {
			out.Data[i] = val
		} else {
			out.Data[i] = 0
		}
	}
	return out
}

func (r *ReLU) Backward(outputGrad *Tensor) *Tensor {
	inGrad := NewTensor(outputGrad.Shape[0], outputGrad.Shape[1], outputGrad.Shape[2])
	for i, val := range r.Input.Data {
		if val > 0 {
			inGrad.Data[i] = outputGrad.Data[i]
		} else {
			inGrad.Data[i] = 0
		}
	}
	return inGrad
}

func (r *ReLU) Update(lr float64) {}

type Dense struct {
	InSize     int
	OutSize    int
	Weights    []float64
	Biases     []float64
	WeightGrad []float64
	BiasGrad   []float64
	Input      *Tensor
}

func NewDense(inSize, outSize int) *Dense {
	return &Dense{
		InSize:     inSize,
		OutSize:    outSize,
		Weights:    make([]float64, outSize*inSize),
		Biases:     make([]float64, outSize),
		WeightGrad: make([]float64, outSize*inSize),
		BiasGrad:   make([]float64, outSize),
	}
}

func (d *Dense) Forward(input *Tensor) *Tensor {
	d.Input = input
	out := NewTensor(d.OutSize, 1, 1)
	for i := 0; i < d.OutSize; i++ {
		sum := d.Biases[i]
		for j := 0; j < d.InSize; j++ {
			sum += d.Weights[i*d.InSize+j] * input.Data[j]
		}
		out.Data[i] = sum
	}
	return out
}

func (d *Dense) Backward(outputGrad *Tensor) *Tensor {
	inGrad := NewTensor(d.Input.Shape[0], d.Input.Shape[1], d.Input.Shape[2])
	for i := 0; i < d.OutSize; i++ {
		dY := outputGrad.Data[i]
		d.BiasGrad[i] += dY
		for j := 0; j < d.InSize; j++ {
			d.WeightGrad[i*d.InSize+j] += dY * d.Input.Data[j]
			inGrad.Data[j] += dY * d.Weights[i*d.InSize+j]
		}
	}
	return inGrad
}

func (d *Dense) Update(lr float64) {
	for i := range d.Weights {
		d.Weights[i] -= lr * d.WeightGrad[i]
		d.WeightGrad[i] = 0
	}
	for i := range d.Biases {
		d.Biases[i] -= lr * d.BiasGrad[i]
		d.BiasGrad[i] = 0
	}
}
