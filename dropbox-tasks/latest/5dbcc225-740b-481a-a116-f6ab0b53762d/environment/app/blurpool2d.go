package main

type BlurPool2D struct {
	PoolSize int
	Stride   int
	Input    *Tensor
}

func NewBlurPool2D(poolSize, stride int) *BlurPool2D {
	return &BlurPool2D{
		PoolSize: poolSize,
		Stride:   stride,
	}
}

func (bp *BlurPool2D) Forward(input *Tensor) *Tensor {
	panic("not implemented")
}

func (bp *BlurPool2D) Backward(outputGrad *Tensor) *Tensor {
	panic("not implemented")
}
