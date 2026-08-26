package pso
import "testing"
func TestCacheNodeLoad(t *testing.T) {
	if CacheNodeLoad([]float64{0, 0}) != 0 {
		t.Fatal("sphere at 0 should be 0")
	}
}
