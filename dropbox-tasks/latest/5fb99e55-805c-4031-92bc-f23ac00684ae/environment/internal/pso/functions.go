package pso

import "math"

// ObjectiveFunction defines the mathematical profile evaluation signature for system-administration resource parameter tuning.
type ObjectiveFunction func([]float64) float64

// GetFunction retrieves the configured system-administration load profile function by name.
func GetFunction(name string) ObjectiveFunction {
	switch name {
	case "sphere", "service_profile_c", "cache_node_load":
		return CacheNodeLoad
	case "rosenbrock", "service_profile_a", "web_cluster_load":
		return WebClusterLoad
	case "rastrigin", "service_profile_b", "db_cluster_load":
		return DBClusterLoad
	default:
		panic("unknown function: " + name)
	}
}

// CacheNodeLoad evaluates the Server Profile C (cache node quota variance) quadratic divergence across system dimensions.
func CacheNodeLoad(x []float64) float64 {
	sum := 0.0
	for _, v := range x {
		sum += v * v
	}
	return sum
}

// WebClusterLoad evaluates the Server Profile A (web cluster non-linear resource drift) valley cost across system dimensions.
func WebClusterLoad(x []float64) float64 {
	sum := 0.0
	for i := 0; i < len(x)-1; i++ {
		term1 := x[i+1] - x[i]*x[i]
		term2 := 1.0 - x[i]
		sum += 100.0*term1*term1 + term2*term2
	}
	return sum
}

// DBClusterLoad evaluates the Server Profile B (database cluster multi-modal harmonic interference) cost across system dimensions.
func DBClusterLoad(x []float64) float64 {
	sum := 10.0 * float64(len(x))
	for _, v := range x {
		sum += v*v - 10.0*math.Cos(2.0*math.Pi*v)
	}
	return sum
}

// ResourceDistance returns the L2-norm (distance from origin) of a position vector.
func ResourceDistance(x []float64) float64 {
	sum := 0.0
	for _, v := range x {
		sum += v * v
	}
	return math.Sqrt(sum)
}
