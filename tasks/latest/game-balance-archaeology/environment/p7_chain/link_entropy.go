package p7_chain

import "balance_lab/p5_div"

func eraDiversity(shares []float64) float64 {
	return p5_div.NormEntropy(shares)
}
