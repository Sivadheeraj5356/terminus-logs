package main

import (
	"fmt"
	"math"
	"testing"
)

type SimpleRNG struct {
	state uint32
}

func NewRNG(seed uint32) *SimpleRNG {
	return &SimpleRNG{state: seed}
}

func (r *SimpleRNG) NextFloat() float64 {
	r.state = r.state*1103515245 + 12345
	return float64(r.state&0x7FFFFFFF) / 2147483647.0
}

func (r *SimpleRNG) Fill(data []float64) {
	for i := range data {
		data[i] = r.NextFloat()*2.0 - 1.0
	}
}

func relativeError(a, b float64) float64 {
	if a == 0 && b == 0 {
		return 0
	}
	diff := math.Abs(a - b)
	denom := math.Abs(a) + math.Abs(b)
	if denom < 1e-8 {
		return diff
	}
	return diff / denom
}

func TestDeformableConv2DGradientCheck(t *testing.T) {
	rng := NewRNG(42)

	testCases := []struct {
		inC, outC, inH, inW int
		kSize, stride, padding int
		groups int
	}{
		{2, 2, 6, 6, 3, 1, 1, 2},
		{1, 2, 5, 5, 2, 2, 0, 1},
		{2, 2, 7, 7, 3, 2, 2, 2},
	}

	for tcIdx, tc := range testCases {
		t.Run(fmt.Sprintf("Case%d", tcIdx), func(t *testing.T) {
			conv := NewDeformableConv2D(tc.inC, tc.outC, tc.kSize, tc.stride, tc.padding, tc.inH, tc.inW, tc.groups)
			rng.Fill(conv.Weights)
			rng.Fill(conv.Biases)
			rng.Fill(conv.OffsetWeights)
			rng.Fill(conv.OffsetBiases)

			input := NewTensor(tc.inC, tc.inH, tc.inW)
			rng.Fill(input.Data)

			conv.Training = true
			output := conv.Forward(input)

			dOutput := NewTensor(output.Shape[0], output.Shape[1], output.Shape[2])
			rng.Fill(dOutput.Data)

			conv.Training = false
			dInput := conv.Backward(dOutput)

			eps := 1e-5

			for i := range conv.Weights {
				oldW := conv.Weights[i]

				conv.Weights[i] = oldW + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				conv.Weights[i] = oldW - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				conv.Weights[i] = oldW

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := conv.WeightGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D WeightGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range conv.Biases {
				oldB := conv.Biases[i]

				conv.Biases[i] = oldB + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				conv.Biases[i] = oldB - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				conv.Biases[i] = oldB

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := conv.BiasGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D BiasGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range conv.OffsetWeights {
				oldOW := conv.OffsetWeights[i]

				conv.OffsetWeights[i] = oldOW + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				conv.OffsetWeights[i] = oldOW - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				conv.OffsetWeights[i] = oldOW

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := conv.OffsetWGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D OffsetWGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range conv.OffsetBiases {
				oldOB := conv.OffsetBiases[i]

				conv.OffsetBiases[i] = oldOB + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				conv.OffsetBiases[i] = oldOB - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				conv.OffsetBiases[i] = oldOB

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := conv.OffsetBGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D OffsetBGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range conv.SplineAlpha {
				oldSA := conv.SplineAlpha[i]

				conv.SplineAlpha[i] = oldSA + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				conv.SplineAlpha[i] = oldSA - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				conv.SplineAlpha[i] = oldSA

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := conv.SplineAlphaGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D SplineAlphaGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range input.Data {
				oldVal := input.Data[i]

				input.Data[i] = oldVal + eps
				outP := conv.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				input.Data[i] = oldVal - eps
				outM := conv.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				input.Data[i] = oldVal

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := dInput.Data[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("DeformableConv2D InputGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			offsetsWUsed := false
			for i := range conv.OffsetWGrad {
				if conv.OffsetWGrad[i] != 0 {
					offsetsWUsed = true
					break
				}
			}
			if !offsetsWUsed {
				t.Error("OffsetWeights have zero gradients")
			}

			offsetsBUsed := false
			for i := range conv.OffsetBGrad {
				if conv.OffsetBGrad[i] != 0 {
					offsetsBUsed = true
					break
				}
			}
			if !offsetsBUsed {
				t.Error("OffsetBiases have zero gradients")
			}
			
			splineAUsed := false
			for i := range conv.SplineAlphaGrad {
				if conv.SplineAlphaGrad[i] != 0 {
					splineAUsed = true
					break
				}
			}
			if !splineAUsed {
				t.Error("SplineAlpha has zero gradients")
			}
		})
	}
}

func TestGroupEvoNorm2DGradientCheck(t *testing.T) {
	rng := NewRNG(123)

	gnCases := []struct {
		channels, groups, H, W int
	}{
		{4, 2, 3, 3},
		{6, 3, 5, 4},
		{2, 1, 2, 2},
	}

	for tcIdx, tc := range gnCases {
		t.Run(fmt.Sprintf("Case%d", tcIdx), func(t *testing.T) {
			inC, numGroups, inH, inW := tc.channels, tc.groups, tc.H, tc.W
			gn := NewGroupEvoNorm2D(inC, numGroups)
			rng.Fill(gn.Gammas)
			rng.Fill(gn.Betas)
			rng.Fill(gn.V)

			input := NewTensor(inC, inH, inW)
			rng.Fill(input.Data)

			output := gn.Forward(input)

			dOutput := NewTensor(output.Shape[0], output.Shape[1], output.Shape[2])
			rng.Fill(dOutput.Data)

			dInput := gn.Backward(dOutput)

			eps := 1e-5

			for i := range gn.Gammas {
				oldG := gn.Gammas[i]

				gn.Gammas[i] = oldG + eps
				outP := gn.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				gn.Gammas[i] = oldG - eps
				outM := gn.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				gn.Gammas[i] = oldG

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := gn.GammaGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("GroupEvoNorm2D GammaGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range gn.Betas {
				oldB := gn.Betas[i]

				gn.Betas[i] = oldB + eps
				outP := gn.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				gn.Betas[i] = oldB - eps
				outM := gn.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				gn.Betas[i] = oldB

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := gn.BetaGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("GroupEvoNorm2D BetaGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range gn.V {
				oldV := gn.V[i]

				gn.V[i] = oldV + eps
				outP := gn.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				gn.V[i] = oldV - eps
				outM := gn.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				gn.V[i] = oldV

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := gn.VGrad[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("GroupEvoNorm2D VGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}

			for i := range input.Data {
				oldVal := input.Data[i]

				input.Data[i] = oldVal + eps
				outP := gn.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				input.Data[i] = oldVal - eps
				outM := gn.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				input.Data[i] = oldVal

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := dInput.Data[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("GroupEvoNorm2D InputGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}
		})
	}
}

func TestBlurPool2DGradientCheck(t *testing.T) {
	rng := NewRNG(777)

	poolCases := []struct {
		inC, H, W, pool, stride int
	}{
		{2, 4, 4, 2, 2},
		{3, 6, 6, 3, 2},
		{1, 5, 5, 2, 1},
	}

	for tcIdx, tc := range poolCases {
		t.Run(fmt.Sprintf("Case%d", tcIdx), func(t *testing.T) {
			inC, inH, inW := tc.inC, tc.H, tc.W
			poolSize, stride := tc.pool, tc.stride

			pool := NewBlurPool2D(poolSize, stride)

			input := NewTensor(inC, inH, inW)
			for i := range input.Data {
				input.Data[i] = float64(i) + rng.NextFloat()*0.1
			}

			output := pool.Forward(input)

			dOutput := NewTensor(output.Shape[0], output.Shape[1], output.Shape[2])
			rng.Fill(dOutput.Data)

			dInput := pool.Backward(dOutput)

			eps := 1e-5
			for i := range input.Data {
				oldVal := input.Data[i]

				input.Data[i] = oldVal + eps
				outP := pool.Forward(input)
				lossP := 0.0
				for j, dy := range dOutput.Data {
					lossP += outP.Data[j] * dy
				}

				input.Data[i] = oldVal - eps
				outM := pool.Forward(input)
				lossM := 0.0
				for j, dy := range dOutput.Data {
					lossM += outM.Data[j] * dy
				}

				input.Data[i] = oldVal

				numGrad := (lossP - lossM) / (2.0 * eps)
				anaGrad := dInput.Data[i]
				relErr := relativeError(anaGrad, numGrad)

				if relErr > 1e-5 && math.Abs(anaGrad-numGrad) > 1e-5 {
					t.Errorf("BlurPool2D InputGrad[%d] mismatch: analytical=%f, numerical=%f, relErr=%f", i, anaGrad, numGrad, relErr)
				}
			}
		})
	}
}

func TestModelTrainingConvergence(t *testing.T) {
	rng := NewRNG(101)

	net := NewNetwork()

	conv := NewDeformableConv2D(2, 4, 3, 1, 1, 8, 8, 2)
	rng.Fill(conv.Weights)
	rng.Fill(conv.Biases)
	rng.Fill(conv.OffsetWeights)
	rng.Fill(conv.OffsetBiases)
	rng.Fill(conv.SplineAlpha)
	net.Add(conv)

	gn := NewGroupEvoNorm2D(4, 2)
	rng.Fill(gn.Gammas)
	rng.Fill(gn.Betas)
	rng.Fill(gn.V)
	net.Add(gn)

	pool := NewBlurPool2D(2, 2)
	net.Add(pool)

	dense := NewDense(4*4*4, 2)
	rng.Fill(dense.Weights)
	rng.Fill(dense.Biases)
	net.Add(dense)

	s0 := NewTensor(2, 8, 8)
	for i := 0; i < 8; i++ {
		s0.Set(0, i, 3, 1.0)
		s0.Set(0, i, 4, 1.0)
		s0.Set(1, i, 3, 1.0)
		s0.Set(1, i, 4, 1.0)
	}

	s1 := NewTensor(2, 8, 8)
	for i := 0; i < 8; i++ {
		s1.Set(0, 3, i, 1.0)
		s1.Set(0, 4, i, 1.0)
		s1.Set(1, 3, i, 1.0)
		s1.Set(1, 4, i, 1.0)
	}

	s2 := NewTensor(2, 8, 8)
	for i := 0; i < 8; i++ {
		s2.Set(0, i, 1, 1.0)
		s2.Set(0, i, 2, 1.0)
		s2.Set(1, i, 1, 1.0)
		s2.Set(1, i, 2, 1.0)
	}

	s3 := NewTensor(2, 8, 8)
	for i := 0; i < 8; i++ {
		s3.Set(0, 1, i, 1.0)
		s3.Set(0, 2, i, 1.0)
		s3.Set(1, 1, i, 1.0)
		s3.Set(1, 2, i, 1.0)
	}

	samples := []*Tensor{s0, s1, s2, s3}
	targets := []int{0, 1, 0, 1}

	lr := 0.05
	var lastLoss float64
	for epoch := 0; epoch < 100; epoch++ {
		totalLoss := 0.0
		for i, x := range samples {
			logits := net.Forward(x)
			loss, dLogits := SoftmaxCrossEntropyLoss(logits, targets[i])
			totalLoss += loss
			net.Backward(dLogits)
			net.Update(lr)
		}
		lastLoss = totalLoss / float64(len(samples))
	}

	fmt.Printf("Final training loss: %f\n", lastLoss)
	if lastLoss >= 0.1 {
		t.Errorf("Expected training loss to converge to < 0.1, got %f", lastLoss)
	}
}

func TestDeformableConv2DGoldenOutputs(t *testing.T) {
	conv := NewDeformableConv2D(2, 2, 3, 1, 1, 3, 3, 2)

	for i := 0; i < 9; i++ {
		conv.Weights[i] = 0.1 * float64(i+1)
		conv.Weights[9+i] = 1.0 + 0.1 * float64(i+1)
	}

	for i := range conv.OffsetWeights {
		conv.OffsetWeights[i] = 0.0
	}
	for i := range conv.OffsetBiases {
		conv.OffsetBiases[i] = 0.0
	}

	input := NewTensor(2, 3, 3)
	for h := 0; h < 3; h++ {
		for w := 0; w < 3; w++ {
			input.Set(0, h, w, 1.0)
			input.Set(1, h, w, 2.0)
		}
	}

	conv.Training = true
	_ = conv.Forward(input)

	expectedW := []float64{
		-0.516398, -0.387298, -0.258199, -0.129100, 0.0, 0.129100, 0.258199, 0.387298, 0.516398,
	}

	for i := 0; i < 9; i++ {
		if math.Abs(conv.tildeW[i]-expectedW[i]) > 1e-4 {
			t.Errorf("Group 0 normalized weight[%d] mismatch: expected %f, got %f", i, expectedW[i], conv.tildeW[i])
		}
		if math.Abs(conv.tildeW[9+i]-expectedW[i]) > 1e-4 {
			t.Errorf("Group 1 normalized weight[%d] mismatch: expected %f, got %f", i, expectedW[i], conv.tildeW[9+i])
		}
	}

	if len(conv.hatW) != 18 {
		t.Error("hatW not populated correctly")
	}
	if len(conv.mu) != 2 {
		t.Error("mu not populated correctly")
	}
	if len(conv.varVal) != 2 {
		t.Error("varVal not populated correctly")
	}
	if len(conv.U) != 2 {
		t.Error("U not populated correctly")
	}
	if len(conv.V) != 18 {
		t.Error("V not populated correctly")
	}
	if len(conv.bjorckW) != 3 {
		t.Error("bjorckW missing iterations")
	}

	conv.OffsetBiases[2] = 100.0

	conv.Training = false
	output := conv.Forward(input)

	expectedOut_c0_00 := 0.516398
	expectedOut_c1_00 := 1.032796
	expectedOut_c0_11 := 0.193649
	expectedOut_c1_11 := 0.387298

	if math.Abs(output.Get(0, 0, 0)-expectedOut_c0_00) > 1e-4 {
		t.Errorf("Golden output at c0,0,0 mismatch: expected %f, got %f", expectedOut_c0_00, output.Get(0, 0, 0))
	}
	if math.Abs(output.Get(1, 0, 0)-expectedOut_c1_00) > 1e-4 {
		t.Errorf("Golden output at c1,0,0 mismatch: expected %f, got %f", expectedOut_c1_00, output.Get(1, 0, 0))
	}
	if math.Abs(output.Get(0, 1, 1)-expectedOut_c0_11) > 1e-4 {
		t.Errorf("Golden output at c0,1,1 mismatch: expected %f, got %f", expectedOut_c0_11, output.Get(0, 1, 1))
	}
	if math.Abs(output.Get(1, 1, 1)-expectedOut_c1_11) > 1e-4 {
		t.Errorf("Golden output at c1,1,1 mismatch: expected %f, got %f", expectedOut_c1_11, output.Get(1, 1, 1))
	}
}

func TestGradientAccumulationAndReset(t *testing.T) {
	conv := NewDeformableConv2D(2, 2, 3, 1, 1, 3, 3, 2)
	rng := NewRNG(123)
	rng.Fill(conv.Weights)
	rng.Fill(conv.Biases)
	rng.Fill(conv.OffsetWeights)
	rng.Fill(conv.OffsetBiases)

	input := NewTensor(2, 3, 3)
	rng.Fill(input.Data)

	conv.Training = true
	output := conv.Forward(input)

	dOutput := NewTensor(output.Shape[0], output.Shape[1], output.Shape[2])
	rng.Fill(dOutput.Data)

	conv.Training = false
	_ = conv.Backward(dOutput)

	gW1 := make([]float64, len(conv.WeightGrad))
	copy(gW1, conv.WeightGrad)
	gB1 := make([]float64, len(conv.BiasGrad))
	copy(gB1, conv.BiasGrad)
	gOW1 := make([]float64, len(conv.OffsetWGrad))
	copy(gOW1, conv.OffsetWGrad)
	gOB1 := make([]float64, len(conv.OffsetBGrad))
	copy(gOB1, conv.OffsetBGrad)
	gSA1 := make([]float64, len(conv.SplineAlphaGrad))
	copy(gSA1, conv.SplineAlphaGrad)

	_ = conv.Backward(dOutput)

	for i := range conv.WeightGrad {
		if math.Abs(conv.WeightGrad[i]-2*gW1[i]) > 1e-9 {
			t.Errorf("WeightGrad[%d] did not accumulate correctly: expected %f, got %f", i, 2*gW1[i], conv.WeightGrad[i])
		}
	}
	for i := range conv.BiasGrad {
		if math.Abs(conv.BiasGrad[i]-2*gB1[i]) > 1e-9 {
			t.Errorf("BiasGrad[%d] did not accumulate correctly: expected %f, got %f", i, 2*gB1[i], conv.BiasGrad[i])
		}
	}
	for i := range conv.OffsetWGrad {
		if math.Abs(conv.OffsetWGrad[i]-2*gOW1[i]) > 1e-9 {
			t.Errorf("OffsetWGrad[%d] did not accumulate correctly: expected %f, got %f", i, 2*gOW1[i], conv.OffsetWGrad[i])
		}
	}
	for i := range conv.OffsetBGrad {
		if math.Abs(conv.OffsetBGrad[i]-2*gOB1[i]) > 1e-9 {
			t.Errorf("OffsetBGrad[%d] did not accumulate correctly: expected %f, got %f", i, 2*gOB1[i], conv.OffsetBGrad[i])
		}
	}
	for i := range conv.SplineAlphaGrad {
		if math.Abs(conv.SplineAlphaGrad[i]-2*gSA1[i]) > 1e-9 {
			t.Errorf("SplineAlphaGrad[%d] did not accumulate correctly: expected %f, got %f", i, 2*gSA1[i], conv.SplineAlphaGrad[i])
		}
	}

	oldWeights := make([]float64, len(conv.Weights))
	copy(oldWeights, conv.Weights)
	conv.Update(0.1)

	for i := range conv.Weights {
		accumulatedGW := 2.0 * gW1[i]
		if math.Abs(conv.Weights[i]-(oldWeights[i]-0.1*accumulatedGW)) > 1e-9 {
			t.Errorf("Weight update incorrect: expected %f, got %f", oldWeights[i]-0.1*accumulatedGW, conv.Weights[i])
		}
		if conv.WeightGrad[i] != 0.0 {
			t.Errorf("WeightGrad[%d] not reset to 0 after Update", i)
		}
	}
	for i := range conv.BiasGrad {
		if conv.BiasGrad[i] != 0.0 {
			t.Errorf("BiasGrad[%d] not reset to 0 after Update", i)
		}
	}
	for i := range conv.OffsetWGrad {
		if conv.OffsetWGrad[i] != 0.0 {
			t.Errorf("OffsetWGrad[%d] not reset to 0 after Update", i)
		}
	}
	for i := range conv.OffsetBGrad {
		if conv.OffsetBGrad[i] != 0.0 {
			t.Errorf("OffsetBGrad[%d] not reset to 0 after Update", i)
		}
	}
	for i := range conv.SplineAlphaGrad {
		if conv.SplineAlphaGrad[i] != 0.0 {
			t.Errorf("SplineAlphaGrad[%d] not reset to 0 after Update", i)
		}
	}
}
