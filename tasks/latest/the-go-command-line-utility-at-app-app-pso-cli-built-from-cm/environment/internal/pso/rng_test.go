package pso
import "testing"
func TestRNG(t *testing.T) {
	rng := NewLCG(42)
	if rng.Float64() < 0 {
		t.Fatal("rng generated negative value")
	}
}
