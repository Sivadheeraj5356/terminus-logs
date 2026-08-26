#!/bin/bash

# Overwrite conv2d.go
cat << 'EOF' > /app/conv2d.go
package main

import (
	"math"
)

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
	c := &DeformableConv2D{
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
		U:             make([]float64, outChannels),
		V:             make([]float64, inChannels*kernelSize*kernelSize),
		Training:      true,
		Offsets:       make([]float64, 2*kernelSize*kernelSize*outH*outW),
		Masks:         make([]float64, kernelSize*kernelSize*outH*outW),
	}
	for i := range c.U {
		c.U[i] = 1.0
	}
	for i := range c.V {
		c.V[i] = 1.0
	}
	for i := 0; i < inChannels; i++ {
		c.SplineAlpha[i] = -0.5
	}
	return c
}

func R(t, a float64) float64 {
	absT := math.Abs(t)
	if absT <= 1 {
		return (a+2)*absT*absT*absT - (a+3)*absT*absT + 1
	} else if absT < 2 {
		return a*absT*absT*absT - 5*a*absT*absT + 8*a*absT - 4*a
	}
	return 0
}

func dRda(t float64) float64 {
	absT := math.Abs(t)
	if absT <= 1 {
		return absT*absT*absT - absT*absT
	} else if absT < 2 {
		return absT*absT*absT - 5*absT*absT + 8*absT - 4
	}
	return 0
}

func dRdt(t, a float64) float64 {
	absT := math.Abs(t)
	signT := 1.0
	if t < 0 {
		signT = -1.0
	}
	if absT <= 1 {
		return signT * (3*(a+2)*absT*absT - 2*(a+3)*absT)
	} else if absT < 2 {
		return signT * (3*a*absT*absT - 10*a*absT + 8*a)
	}
	return 0
}

func sigmoid(x float64) float64 {
	return 1.0 / (1.0 + math.Exp(-x))
}

func (c *DeformableConv2D) Forward(input *Tensor) *Tensor {
	c.Input = input.Clone()
	out := NewTensor(c.OutChannels, c.OutH, c.OutW)

	Mg := c.OutChannels / c.Groups
	Ng := (c.InChannels / c.Groups) * c.KernelSize * c.KernelSize
	c.hatW = make([]float64, len(c.Weights))
	c.mu = make([]float64, c.OutChannels)
	c.varVal = make([]float64, c.OutChannels)
	c.sigma = make([]float64, c.Groups)
	c.tildeW = make([]float64, len(c.Weights))
	c.bjorckW = make([][]float64, 3)
	for i := range c.bjorckW {
		c.bjorckW[i] = make([]float64, len(c.Weights))
	}

	W0 := make([]float64, len(c.Weights))
	for g := 0; g < c.Groups; g++ {
		groupOffset := g * Mg * Ng
		for i := 0; i < Mg; i++ {
			sum := 0.0
			for j := 0; j < Ng; j++ {
				sum += c.Weights[groupOffset+i*Ng+j]
			}
			mu := sum / float64(Ng)
			c.mu[g*Mg+i] = mu

			varSum := 0.0
			for j := 0; j < Ng; j++ {
				diff := c.Weights[groupOffset+i*Ng+j] - mu
				varSum += diff * diff
			}
			varVal := varSum / float64(Ng)
			c.varVal[g*Mg+i] = varVal

			std := math.Sqrt(varVal + 1e-5)
			for j := 0; j < Ng; j++ {
				c.hatW[groupOffset+i*Ng+j] = (c.Weights[groupOffset+i*Ng+j] - mu) / std
			}
		}

		if c.Training {
			for it := 0; it < 5; it++ {
				var vNormSq float64
				for j := 0; j < Ng; j++ {
					sum := 0.0
					for i := 0; i < Mg; i++ {
						sum += c.hatW[groupOffset+i*Ng+j] * c.U[g*Mg+i]
					}
					c.V[g*Ng+j] = sum
					vNormSq += sum * sum
				}
				vNorm := math.Sqrt(vNormSq)
				if vNorm > 0 {
					for j := 0; j < Ng; j++ {
						c.V[g*Ng+j] /= vNorm
					}
				}

				var uNormSq float64
				for i := 0; i < Mg; i++ {
					sum := 0.0
					for j := 0; j < Ng; j++ {
						sum += c.hatW[groupOffset+i*Ng+j] * c.V[g*Ng+j]
					}
					c.U[g*Mg+i] = sum
					uNormSq += sum * sum
				}
				uNorm := math.Sqrt(uNormSq)
				if uNorm > 0 {
					for i := 0; i < Mg; i++ {
						c.U[g*Mg+i] /= uNorm
					}
				}
			}
		}

		sigma := 0.0
		for i := 0; i < Mg; i++ {
			sum := 0.0
			for j := 0; j < Ng; j++ {
				sum += c.hatW[groupOffset+i*Ng+j] * c.V[g*Ng+j]
			}
			sigma += c.U[g*Mg+i] * sum
		}
		c.sigma[g] = sigma

		for i := 0; i < Mg; i++ {
			for j := 0; j < Ng; j++ {
				W0[groupOffset+i*Ng+j] = c.hatW[groupOffset+i*Ng+j] / sigma
			}
		}
	}

	curW := W0
	for t := 0; t < 3; t++ {
		nextW := make([]float64, len(c.Weights))
		for g := 0; g < c.Groups; g++ {
			groupOffset := g * Mg * Ng
			for i := 0; i < Mg; i++ {
				for j := 0; j < Ng; j++ {
					wtij := curW[groupOffset+i*Ng+j]
					
					var wt_wt_wt float64
					for k := 0; k < Mg; k++ {
						dot := 0.0
						for l := 0; l < Ng; l++ {
							dot += curW[groupOffset+i*Ng+l] * curW[groupOffset+k*Ng+l]
						}
						wt_wt_wt += dot * curW[groupOffset+k*Ng+j]
					}
					nextW[groupOffset+i*Ng+j] = 1.5*wtij - 0.5*wt_wt_wt
				}
			}
		}
		copy(c.bjorckW[t], nextW)
		curW = nextW
	}
	copy(c.tildeW, curW)

	cOff := 3 * c.KernelSize * c.KernelSize
	P := NewTensor(cOff, c.OutH, c.OutW)
	for oh := 0; oh < c.OutH; oh++ {
		for ow := 0; ow < c.OutW; ow++ {
			for coff := 0; coff < cOff; coff++ {
				sum := c.OffsetBiases[coff]
				for ic := 0; ic < c.InChannels; ic++ {
					for kh := 0; kh < c.KernelSize; kh++ {
						for kw := 0; kw < c.KernelSize; kw++ {
							ih := oh*c.Stride - c.Padding + kh
							iw := ow*c.Stride - c.Padding + kw
							if ih >= 0 && ih < c.InH && iw >= 0 && iw < c.InW {
								idxW := ((coff*c.InChannels+ic)*c.KernelSize+kh)*c.KernelSize + kw
								sum += c.OffsetWeights[idxW] * input.Get(ic, ih, iw)
							}
						}
					}
				}
				P.Set(coff, oh, ow, sum)
			}
		}
	}

	K2 := c.KernelSize * c.KernelSize
	kh_c := float64(c.KernelSize-1) / 2.0
	kw_c := float64(c.KernelSize-1) / 2.0

	for oh := 0; oh < c.OutH; oh++ {
		for ow := 0; ow < c.OutW; ow++ {
			y_center := float64(oh*c.Stride-c.Padding) + kh_c
			x_center := float64(ow*c.Stride-c.Padding) + kw_c

			for kh := 0; kh < c.KernelSize; kh++ {
				for kw := 0; kw < c.KernelSize; kw++ {
					k := kh*c.KernelSize + kw
					dy_k := float64(kh) - kh_c
					dx_k := float64(kw) - kw_c
					r_k := math.Sqrt(dy_k*dy_k + dx_k*dx_k)
					theta_k := math.Atan2(dy_k, dx_k)

					o_r := P.Get(2*k, oh, ow)
					o_theta := P.Get(2*k+1, oh, ow)
					raw_m := P.Get(2*K2+k, oh, ow)

					dr := 2.0 * math.Tanh(o_r)
					dtheta := math.Pi * math.Tanh(o_theta)
					
					c.Offsets[2*(k*c.OutH*c.OutW + oh*c.OutW + ow)] = dr
					c.Offsets[2*(k*c.OutH*c.OutW + oh*c.OutW + ow)+1] = dtheta
					
					R_k := r_k + dr
					Theta_k := theta_k + dtheta
					
					y_a := y_center + R_k*math.Sin(Theta_k)
					x_a := x_center + R_k*math.Cos(Theta_k)
					
					mask := sigmoid(raw_m)
					c.Masks[k*c.OutH*c.OutW + oh*c.OutW + ow] = mask

					for oc := 0; oc < c.OutChannels; oc++ {
						g := oc / (c.OutChannels / c.Groups)
						oc_local := oc % (c.OutChannels / c.Groups)
						Cin_g := c.InChannels / c.Groups

						sum := 0.0
						for ic_local := 0; ic_local < Cin_g; ic_local++ {
							ic := g*Cin_g + ic_local
							alpha := c.SplineAlpha[ic]

							y0 := math.Floor(y_a)
							x0 := math.Floor(x_a)
							dy := y_a - y0
							dx := x_a - x0

							interp := 0.0
							for m := -1; m <= 2; m++ {
								for n := -1; n <= 2; n++ {
									iy := int(y0) + m
									ix := int(x0) + n
									if iy >= 0 && iy < c.InH && ix >= 0 && ix < c.InW {
										interp += input.Get(ic, iy, ix) * R(float64(m)-dy, alpha) * R(float64(n)-dx, alpha)
									}
								}
							}
							
							wt := c.tildeW[((g*(c.OutChannels/c.Groups)+oc_local)*Cin_g+ic_local)*c.KernelSize*c.KernelSize + kh*c.KernelSize + kw]
							sum += wt * interp * mask
						}
						out.Set(oc, oh, ow, out.Get(oc, oh, ow)+sum)
					}
				}
			}
			for oc := 0; oc < c.OutChannels; oc++ {
				out.Set(oc, oh, ow, out.Get(oc, oh, ow)+c.Biases[oc])
			}
		}
	}
	return out
}

func (c *DeformableConv2D) Backward(outputGrad *Tensor) *Tensor {
	inputGrad := NewTensor(c.InChannels, c.InH, c.InW)
	dP := NewTensor(3*c.KernelSize*c.KernelSize, c.OutH, c.OutW)
	dtildeW := make([]float64, len(c.Weights))

	K2 := c.KernelSize * c.KernelSize
	kh_c := float64(c.KernelSize-1) / 2.0
	kw_c := float64(c.KernelSize-1) / 2.0

	for oh := 0; oh < c.OutH; oh++ {
		for ow := 0; ow < c.OutW; ow++ {
			y_center := float64(oh*c.Stride-c.Padding) + kh_c
			x_center := float64(ow*c.Stride-c.Padding) + kw_c

			for oc := 0; oc < c.OutChannels; oc++ {
				dy_val := outputGrad.Get(oc, oh, ow)
				c.BiasGrad[oc] += dy_val
			}

			for kh := 0; kh < c.KernelSize; kh++ {
				for kw := 0; kw < c.KernelSize; kw++ {
					k := kh*c.KernelSize + kw
					dy_k := float64(kh) - kh_c
					dx_k := float64(kw) - kw_c
					r_k := math.Sqrt(dy_k*dy_k + dx_k*dx_k)
					theta_k := math.Atan2(dy_k, dx_k)

					dr := c.Offsets[2*(k*c.OutH*c.OutW + oh*c.OutW + ow)]
					dtheta := c.Offsets[2*(k*c.OutH*c.OutW + oh*c.OutW + ow)+1]
					R_k := r_k + dr
					Theta_k := theta_k + dtheta

					y_a := y_center + R_k*math.Sin(Theta_k)
					x_a := x_center + R_k*math.Cos(Theta_k)
					y0 := math.Floor(y_a)
					x0 := math.Floor(x_a)
					dy := y_a - y0
					dx := x_a - x0

					mask := c.Masks[k*c.OutH*c.OutW + oh*c.OutW + ow]

					var dMask, dy_a, dx_a float64

					for oc := 0; oc < c.OutChannels; oc++ {
						g := oc / (c.OutChannels / c.Groups)
						oc_local := oc % (c.OutChannels / c.Groups)
						Cin_g := c.InChannels / c.Groups
						dOut := outputGrad.Get(oc, oh, ow)

						for ic_local := 0; ic_local < Cin_g; ic_local++ {
							ic := g*Cin_g + ic_local
							alpha := c.SplineAlpha[ic]
							wt_idx := ((g*(c.OutChannels/c.Groups)+oc_local)*Cin_g+ic_local)*c.KernelSize*c.KernelSize + kh*c.KernelSize + kw
							wt := c.tildeW[wt_idx]

							interp := 0.0
							dInterp_dy_a := 0.0
							dInterp_dx_a := 0.0
							dInterp_dalpha := 0.0
							
							for m := -1; m <= 2; m++ {
								for n := -1; n <= 2; n++ {
									iy := int(y0) + m
									ix := int(x0) + n
									if iy >= 0 && iy < c.InH && ix >= 0 && ix < c.InW {
										val := c.Input.Get(ic, iy, ix)
										ry := R(float64(m)-dy, alpha)
										rx := R(float64(n)-dx, alpha)
										interp += val * ry * rx
										
										dry := dRdt(float64(m)-dy, alpha) * (-1.0)
										drx := dRdt(float64(n)-dx, alpha) * (-1.0)
										
										dInterp_dy_a += val * dry * rx
										dInterp_dx_a += val * ry * drx
										
										dInterp_dalpha += val * dRda(float64(m)-dy) * rx + val * ry * dRda(float64(n)-dx)
										
										inputGrad.Set(ic, iy, ix, inputGrad.Get(ic, iy, ix) + dOut * wt * mask * ry * rx)
									}
								}
							}

							dtildeW[wt_idx] += dOut * interp * mask
							dMask += dOut * wt * interp
							dy_a += dOut * wt * mask * dInterp_dy_a
							dx_a += dOut * wt * mask * dInterp_dx_a
							c.SplineAlphaGrad[ic] += dOut * wt * mask * dInterp_dalpha
						}
					}

					dR_k := dy_a * math.Sin(Theta_k) + dx_a * math.Cos(Theta_k)
					dTheta_k := dy_a * R_k * math.Cos(Theta_k) - dx_a * R_k * math.Sin(Theta_k)

					ddr := dR_k
					ddtheta := dTheta_k

					d_o_r := ddr * 2.0 * (1.0 - (dr/2.0)*(dr/2.0))
					d_o_theta := ddtheta * math.Pi * (1.0 - (dtheta/math.Pi)*(dtheta/math.Pi))
					d_raw_m := dMask * mask * (1.0 - mask)

					dP.Set(2*k, oh, ow, d_o_r)
					dP.Set(2*k+1, oh, ow, d_o_theta)
					dP.Set(2*K2+k, oh, ow, d_raw_m)
				}
			}
		}
	}

	for oh := 0; oh < c.OutH; oh++ {
		for ow := 0; ow < c.OutW; ow++ {
			for coff := 0; coff < 3*K2; coff++ {
				dP_val := dP.Get(coff, oh, ow)
				c.OffsetBGrad[coff] += dP_val
				for ic := 0; ic < c.InChannels; ic++ {
					for kh := 0; kh < c.KernelSize; kh++ {
						for kw := 0; kw < c.KernelSize; kw++ {
							ih := oh*c.Stride - c.Padding + kh
							iw := ow*c.Stride - c.Padding + kw
							if ih >= 0 && ih < c.InH && iw >= 0 && iw < c.InW {
								idxW := ((coff*c.InChannels+ic)*c.KernelSize+kh)*c.KernelSize + kw
								c.OffsetWGrad[idxW] += dP_val * c.Input.Get(ic, ih, iw)
								inputGrad.Set(ic, ih, iw, inputGrad.Get(ic, ih, iw) + dP_val*c.OffsetWeights[idxW])
							}
						}
					}
				}
			}
		}
	}

	Mg := c.OutChannels / c.Groups
	Ng := (c.InChannels / c.Groups) * c.KernelSize * c.KernelSize

	W0 := make([]float64, len(c.Weights))
	for g := 0; g < c.Groups; g++ {
		groupOffset := g * Mg * Ng
		for i := 0; i < Mg; i++ {
			for j := 0; j < Ng; j++ {
				W0[groupOffset+i*Ng+j] = c.hatW[groupOffset+i*Ng+j] / c.sigma[g]
			}
		}
	}

	dW0 := make([]float64, len(c.Weights))
	dCurW := dtildeW
	for t := 2; t >= 0; t-- {
		dPrevW := make([]float64, len(c.Weights))
		curW := W0
		if t > 0 {
			curW = c.bjorckW[t-1]
		}
		
		for g := 0; g < c.Groups; g++ {
			groupOffset := g * Mg * Ng
			for i := 0; i < Mg; i++ {
				for j := 0; j < Ng; j++ {
					d_nxt := dCurW[groupOffset+i*Ng+j]
					dPrevW[groupOffset+i*Ng+j] += 1.5 * d_nxt
					
					for k := 0; k < Mg; k++ {
						for l := 0; l < Ng; l++ {
							term := curW[groupOffset+i*Ng+l] * curW[groupOffset+k*Ng+l] * curW[groupOffset+k*Ng+j]
							_ = term 
							
							dPrevW[groupOffset+i*Ng+l] -= 0.5 * d_nxt * curW[groupOffset+k*Ng+l] * curW[groupOffset+k*Ng+j]
							dPrevW[groupOffset+k*Ng+l] -= 0.5 * d_nxt * curW[groupOffset+i*Ng+l] * curW[groupOffset+k*Ng+j]
							dPrevW[groupOffset+k*Ng+j] -= 0.5 * d_nxt * curW[groupOffset+i*Ng+l] * curW[groupOffset+k*Ng+l]
						}
					}
				}
			}
		}
		dCurW = dPrevW
	}
	dW0 = dCurW

	for g := 0; g < c.Groups; g++ {
		groupOffset := g * Mg * Ng
		dHatW := make([]float64, Mg*Ng)
		dSigma := 0.0

		for i := 0; i < Mg; i++ {
			for j := 0; j < Ng; j++ {
				dHatW[i*Ng+j] += dW0[groupOffset+i*Ng+j] / c.sigma[g]
				dSigma -= dW0[groupOffset+i*Ng+j] * c.hatW[groupOffset+i*Ng+j] / (c.sigma[g] * c.sigma[g])
			}
		}

		for i := 0; i < Mg; i++ {
			for j := 0; j < Ng; j++ {
				dHatW[i*Ng+j] += dSigma * c.U[g*Mg+i] * c.V[g*Ng+j]
			}
		}

		for i := 0; i < Mg; i++ {
			std := math.Sqrt(c.varVal[g*Mg+i] + 1e-5)
			
			dMu := 0.0
			dVar := 0.0
			for j := 0; j < Ng; j++ {
				dx_hat := dHatW[i*Ng+j]
				dMu -= dx_hat / std
				dVar -= 0.5 * dx_hat * (c.Weights[groupOffset+i*Ng+j] - c.mu[g*Mg+i]) / (std * std * std)
			}
			
			for j := 0; j < Ng; j++ {
				dx_hat := dHatW[i*Ng+j]
				dW := dx_hat / std
				dW += dVar * 2.0 * (c.Weights[groupOffset+i*Ng+j] - c.mu[g*Mg+i]) / float64(Ng)
				dW += dMu / float64(Ng)
				c.WeightGrad[groupOffset+i*Ng+j] += dW
			}
		}
	}

	return inputGrad
}

func (c *DeformableConv2D) Update(lr float64) {
	for i := range c.Weights {
		c.Weights[i] -= lr * c.WeightGrad[i]
		c.WeightGrad[i] = 0
	}
	for i := range c.Biases {
		c.Biases[i] -= lr * c.BiasGrad[i]
		c.BiasGrad[i] = 0
	}
	for i := range c.OffsetWeights {
		c.OffsetWeights[i] -= lr * c.OffsetWGrad[i]
		c.OffsetWGrad[i] = 0
	}
	for i := range c.OffsetBiases {
		c.OffsetBiases[i] -= lr * c.OffsetBGrad[i]
		c.OffsetBGrad[i] = 0
	}
	for i := range c.SplineAlpha {
		c.SplineAlpha[i] -= lr * c.SplineAlphaGrad[i]
		c.SplineAlphaGrad[i] = 0
	}
}
EOF

# Overwrite groupevonorm2d.go
cat << 'EOF' > /app/groupevonorm2d.go
package main

import "math"

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
	mu_g       []float64
	var_g      []float64
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
	gn.Input = input.Clone()
	out := NewTensor(input.Shape[0], input.Shape[1], input.Shape[2])
	
	Cg := gn.Channels / gn.NumGroups
	N := float64(Cg * input.Shape[1] * input.Shape[2])
	
	gn.mu_g = make([]float64, gn.NumGroups)
	gn.var_g = make([]float64, gn.NumGroups)
	
	for g := 0; g < gn.NumGroups; g++ {
		sum := 0.0
		for c := g*Cg; c < (g+1)*Cg; c++ {
			for h := 0; h < input.Shape[1]; h++ {
				for w := 0; w < input.Shape[2]; w++ {
					sum += input.Get(c, h, w)
				}
			}
		}
		mu := sum / N
		gn.mu_g[g] = mu
		
		varSum := 0.0
		for c := g*Cg; c < (g+1)*Cg; c++ {
			for h := 0; h < input.Shape[1]; h++ {
				for w := 0; w < input.Shape[2]; w++ {
					diff := input.Get(c, h, w) - mu
					varSum += diff * diff
				}
			}
		}
		varVal := varSum / N
		gn.var_g[g] = varVal
		
		std := math.Sqrt(varVal + 1e-5)
		
		for c := g*Cg; c < (g+1)*Cg; c++ {
			v := gn.V[c]
			gamma := gn.Gammas[c]
			beta := gn.Betas[c]
			for h := 0; h < input.Shape[1]; h++ {
				for w := 0; w < input.Shape[2]; w++ {
					x := input.Get(c, h, w)
					sig := 1.0 / (1.0 + math.Exp(-(v * x)))
					x_hat := (x * sig) / std
					y := gamma * x_hat + beta
					out.Set(c, h, w, y)
				}
			}
		}
	}
	return out
}

func (gn *GroupEvoNorm2D) Backward(outputGrad *Tensor) *Tensor {
	inputGrad := NewTensor(gn.Input.Shape[0], gn.Input.Shape[1], gn.Input.Shape[2])
	Cg := gn.Channels / gn.NumGroups
	N := float64(Cg * gn.Input.Shape[1] * gn.Input.Shape[2])
	
	for g := 0; g < gn.NumGroups; g++ {
		std := math.Sqrt(gn.var_g[g] + 1e-5)
		mu := gn.mu_g[g]
		
		sum_d_xhat_N := 0.0
		for c := g*Cg; c < (g+1)*Cg; c++ {
			v := gn.V[c]
			for h := 0; h < gn.Input.Shape[1]; h++ {
				for w := 0; w < gn.Input.Shape[2]; w++ {
					x := gn.Input.Get(c, h, w)
					dy := outputGrad.Get(c, h, w)
					sig := 1.0 / (1.0 + math.Exp(-(v * x)))
					x_hat := (x * sig) / std
					
					gn.GammaGrad[c] += dy * x_hat
					gn.BetaGrad[c] += dy
					
					dx_hat := dy * gn.Gammas[c]
					N_j := x * sig
					sum_d_xhat_N += dx_hat * N_j
				}
			}
		}
		
		for c := g*Cg; c < (g+1)*Cg; c++ {
			v := gn.V[c]
			for h := 0; h < gn.Input.Shape[1]; h++ {
				for w := 0; w < gn.Input.Shape[2]; w++ {
					x := gn.Input.Get(c, h, w)
					dy := outputGrad.Get(c, h, w)
					sig := 1.0 / (1.0 + math.Exp(-(v * x)))
					
					dx_hat := dy * gn.Gammas[c]
					
					gn.VGrad[c] += dx_hat * (x * x * sig * (1.0 - sig)) / std
					
					N_prime := sig + x * v * sig * (1.0 - sig)
					
					dx := dx_hat * (N_prime / std) - ((x - mu) / (std * std * std * N)) * sum_d_xhat_N
					
					inputGrad.Set(c, h, w, inputGrad.Get(c, h, w) + dx)
				}
			}
		}
	}
	return inputGrad
}

func (gn *GroupEvoNorm2D) Update(lr float64) {
	for i := range gn.Gammas {
		gn.Gammas[i] -= lr * gn.GammaGrad[i]
		gn.GammaGrad[i] = 0
	}
	for i := range gn.Betas {
		gn.Betas[i] -= lr * gn.BetaGrad[i]
		gn.BetaGrad[i] = 0
	}
	for i := range gn.V {
		gn.V[i] -= lr * gn.VGrad[i]
		gn.VGrad[i] = 0
	}
}
EOF

# Overwrite blurpool2d.go
cat << 'EOF' > /app/blurpool2d.go
package main

type BlurPool2D struct {
	PoolSize int
	Stride   int
	Input    *Tensor
	M        *Tensor
	Argmax_h []int
	Argmax_w []int
}

func NewBlurPool2D(poolSize, stride int) *BlurPool2D {
	return &BlurPool2D{
		PoolSize: poolSize,
		Stride:   stride,
	}
}

func (bp *BlurPool2D) Forward(input *Tensor) *Tensor {
	bp.Input = input.Clone()
	
	Hm := input.Shape[1] - bp.PoolSize + 1
	Wm := input.Shape[2] - bp.PoolSize + 1
	
	bp.M = NewTensor(input.Shape[0], Hm, Wm)
	bp.Argmax_h = make([]int, input.Shape[0]*Hm*Wm)
	bp.Argmax_w = make([]int, input.Shape[0]*Hm*Wm)
	
	for c := 0; c < input.Shape[0]; c++ {
		for h := 0; h < Hm; h++ {
			for w := 0; w < Wm; w++ {
				maxVal := -1e10
				max_h, max_w := 0, 0
				for m := 0; m < bp.PoolSize; m++ {
					for n := 0; n < bp.PoolSize; n++ {
						val := input.Get(c, h+m, w+n)
						if val > maxVal {
							maxVal = val
							max_h = h+m
							max_w = w+n
						}
					}
				}
				bp.M.Set(c, h, w, maxVal)
				idx := (c*Hm + h)*Wm + w
				bp.Argmax_h[idx] = max_h
				bp.Argmax_w[idx] = max_w
			}
		}
	}
	
	Hout := (Hm - 1)/bp.Stride + 1
	Wout := (Wm - 1)/bp.Stride + 1
	out := NewTensor(input.Shape[0], Hout, Wout)
	
	B := [][]float64{
		{1.0/16.0, 2.0/16.0, 1.0/16.0},
		{2.0/16.0, 4.0/16.0, 2.0/16.0},
		{1.0/16.0, 2.0/16.0, 1.0/16.0},
	}
	
	for c := 0; c < input.Shape[0]; c++ {
		for hout := 0; hout < Hout; hout++ {
			for wout := 0; wout < Wout; wout++ {
				sum := 0.0
				for i := 0; i < 3; i++ {
					for j := 0; j < 3; j++ {
						mh := hout*bp.Stride - 1 + i
						mw := wout*bp.Stride - 1 + j
						if mh >= 0 && mh < Hm && mw >= 0 && mw < Wm {
							sum += B[i][j] * bp.M.Get(c, mh, mw)
						}
					}
				}
				out.Set(c, hout, wout, sum)
			}
		}
	}
	
	return out
}

func (bp *BlurPool2D) Backward(outputGrad *Tensor) *Tensor {
	inputGrad := NewTensor(bp.Input.Shape[0], bp.Input.Shape[1], bp.Input.Shape[2])
	
	Hm := bp.M.Shape[1]
	Wm := bp.M.Shape[2]
	dM := NewTensor(bp.Input.Shape[0], Hm, Wm)
	
	B := [][]float64{
		{1.0/16.0, 2.0/16.0, 1.0/16.0},
		{2.0/16.0, 4.0/16.0, 2.0/16.0},
		{1.0/16.0, 2.0/16.0, 1.0/16.0},
	}
	
	for c := 0; c < bp.Input.Shape[0]; c++ {
		for hout := 0; hout < outputGrad.Shape[1]; hout++ {
			for wout := 0; wout < outputGrad.Shape[2]; wout++ {
				dy := outputGrad.Get(c, hout, wout)
				for i := 0; i < 3; i++ {
					for j := 0; j < 3; j++ {
						mh := hout*bp.Stride - 1 + i
						mw := wout*bp.Stride - 1 + j
						if mh >= 0 && mh < Hm && mw >= 0 && mw < Wm {
							dM.Set(c, mh, mw, dM.Get(c, mh, mw) + dy*B[i][j])
						}
					}
				}
			}
		}
	}
	
	for c := 0; c < bp.Input.Shape[0]; c++ {
		for h := 0; h < Hm; h++ {
			for w := 0; w < Wm; w++ {
				idx := (c*Hm + h)*Wm + w
				max_h := bp.Argmax_h[idx]
				max_w := bp.Argmax_w[idx]
				val := inputGrad.Get(c, max_h, max_w)
				inputGrad.Set(c, max_h, max_w, val + dM.Get(c, h, w))
			}
		}
	}
	
	return inputGrad
}

func (bp *BlurPool2D) Update(lr float64) {}
EOF

echo "Done writing oracle solution"
