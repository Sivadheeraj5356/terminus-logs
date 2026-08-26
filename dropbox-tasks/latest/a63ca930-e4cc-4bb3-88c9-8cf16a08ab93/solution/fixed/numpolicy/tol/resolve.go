package tol

func ResolveCircuit(
	normEps float64,
	fidelityEps float64,
	fuseAdjacent bool,
	checkUnitary bool,
	ghostEps float64,
	overrides map[string]interface{},
) (float64, float64, bool, bool, float64) {
	if overrides != nil {
		if v, ok := overrides["norm_eps"]; ok {
			if n, ok := toFloat(v); ok && n > 0 {
				normEps = n
			}
		}
		if v, ok := overrides["fidelity_eps"]; ok {
			if n, ok := toFloat(v); ok && n > 0 {
				fidelityEps = n
			}
		}
		if v, ok := overrides["fuse_adjacent"]; ok {
			if b, ok := toBool(v); ok {
				fuseAdjacent = b
			}
		}
		if v, ok := overrides["check_unitary"]; ok {
			if b, ok := toBool(v); ok {
				checkUnitary = b
			}
		}
		if v, ok := overrides["ghost_eps"]; ok {
			if n, ok := toFloat(v); ok {
				ghostEps = n
			}
		}
	}
	return normEps, fidelityEps, fuseAdjacent, checkUnitary, ghostEps
}

func toBool(v interface{}) (bool, bool) {
	switch x := v.(type) {
	case bool:
		return x, true
	default:
		return false, false
	}
}

func toFloat(v interface{}) (float64, bool) {
	switch x := v.(type) {
	case float64:
		return x, true
	case int:
		return float64(x), true
	default:
		return 0, false
	}
}

func NormDrifted(norm, eps float64) bool {
	d := norm - 1
	if d < 0 {
		d = -d
	}
	return d > eps
}

func FidelityDrifted(fid, eps float64) bool {
	d := fid - 1
	if d < 0 {
		d = -d
	}
	return d > eps
}
