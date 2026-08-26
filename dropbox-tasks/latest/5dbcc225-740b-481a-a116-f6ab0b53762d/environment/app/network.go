package main

import "math"

type Network struct {
	Layers []Layer
}

func NewNetwork() *Network {
	return &Network{}
}

func (n *Network) Add(l Layer) {
	n.Layers = append(n.Layers, l)
}

func (n *Network) Forward(input *Tensor) *Tensor {
	curr := input
	for _, layer := range n.Layers {
		curr = layer.Forward(curr)
	}
	return curr
}

func (n *Network) Backward(lossGrad *Tensor) *Tensor {
	curr := lossGrad
	for i := len(n.Layers) - 1; i >= 0; i-- {
		curr = n.Layers[i].Backward(curr)
	}
	return curr
}

func (n *Network) Update(lr float64) {
	for _, layer := range n.Layers {
		layer.Update(lr)
	}
}

func SoftmaxCrossEntropyLoss(logits *Tensor, target int) (float64, *Tensor) {
	size := logits.Shape[0]
	maxLogit := logits.Data[0]
	for i := 1; i < size; i++ {
		if logits.Data[i] > maxLogit {
			maxLogit = logits.Data[i]
		}
	}

	expVals := make([]float64, size)
	sumExp := 0.0
	for i := 0; i < size; i++ {
		expVals[i] = math.Exp(logits.Data[i] - maxLogit)
		sumExp += expVals[i]
	}

	probTarget := expVals[target] / sumExp
	loss := -math.Log(probTarget)

	grad := NewTensor(size, 1, 1)
	for i := 0; i < size; i++ {
		prob := expVals[i] / sumExp
		if i == target {
			grad.Data[i] = prob - 1.0
		} else {
			grad.Data[i] = prob
		}
	}

	return loss, grad
}
