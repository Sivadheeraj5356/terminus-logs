package kdescore

import "fmt"

func Sample(input Input) (Output, error) {
	results := make([]Result, 0, len(input.Inputs))
	for _, req := range input.Inputs {
		if err := validate(req); err != nil {
			return Output{}, err
		}
		results = append(results, approximate(req))
	}
	return Output{Results: results}, nil
}

func validate(req Request) error {
	if len(req.Signal) == 0 {
		return fmt.Errorf("signal must not be empty")
	}
	if !(req.Sigma > 0) {
		return fmt.Errorf("sigma must be positive")
	}
	return nil
}

func approximate(req Request) Result {
	out := make([]float64, len(req.Signal))
	for i := range req.Signal {
		sum := 0.0
		count := 0.0
		for j := i - 1; j <= i+1; j++ {
			if j >= 0 && j < len(req.Signal) {
				sum += req.Signal[j]
				count += 1
			}
		}
		out[i] = sum / count
	}
	return Result{Filtered: out}
}
