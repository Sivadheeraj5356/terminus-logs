package policy

import (
	"os"
	"strconv"
	"strings"
)

type Policy struct {
	Epoch    int
	MaxIters int
	Tol      float64
}

func Load(path string) Policy {
	p := Policy{Epoch: 1, MaxIters: 5000, Tol: 1e-9}
	b, err := os.ReadFile(path)
	if err != nil {
		return applyEnv(p)
	}
	for _, line := range strings.Split(string(b), "\n") {
		line = strings.TrimSpace(line)
		if strings.HasPrefix(line, "policy_epoch") {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				if v, e := strconv.Atoi(strings.TrimSpace(parts[1])); e == nil {
					p.Epoch = v
				}
			}
		}
		if strings.HasPrefix(line, "max_iters") {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				if v, e := strconv.Atoi(strings.TrimSpace(parts[1])); e == nil {
					p.MaxIters = v
				}
			}
		}
		if strings.HasPrefix(line, "tol") {
			parts := strings.SplitN(line, "=", 2)
			if len(parts) == 2 {
				if v, e := strconv.ParseFloat(strings.TrimSpace(parts[1]), 64); e == nil {
					p.Tol = v
				}
			}
		}
	}
	return applyEnv(p)
}

func applyEnv(p Policy) Policy {
	if v := os.Getenv("MASS_POLICY_EPOCH"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			p.Epoch = n
		}
	}
	return p
}
