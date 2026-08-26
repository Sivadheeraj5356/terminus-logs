package main

type Tensor struct {
	Data  []float64
	Shape [3]int // Channels, Height, Width
}

func NewTensor(c, h, w int) *Tensor {
	return &Tensor{
		Data:  make([]float64, c*h*w),
		Shape: [3]int{c, h, w},
	}
}

func (t *Tensor) Get(c, h, w int) float64 {
	idx := c*t.Shape[1]*t.Shape[2] + h*t.Shape[2] + w
	return t.Data[idx]
}

func (t *Tensor) Set(c, h, w int, val float64) {
	idx := c*t.Shape[1]*t.Shape[2] + h*t.Shape[2] + w
	t.Data[idx] = val
}

func (t *Tensor) Add(c, h, w int, val float64) {
	idx := c*t.Shape[1]*t.Shape[2] + h*t.Shape[2] + w
	t.Data[idx] += val
}

func (t *Tensor) Clone() *Tensor {
	clone := NewTensor(t.Shape[0], t.Shape[1], t.Shape[2])
	copy(clone.Data, t.Data)
	return clone
}

func (t *Tensor) Zero() {
	for i := range t.Data {
		t.Data[i] = 0
	}
}
