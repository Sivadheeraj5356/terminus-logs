package width

import (
	"fmt"
	"os"
	"path/filepath"
)

// Counter tracks the slice counter marker under the workspace.
type Counter struct {
	root string
}

// NewCounter binds a counter to a workspace archive root.
func NewCounter(workspace string) *Counter {
	return &Counter{root: filepath.Join(workspace, "archive")}
}

// Current reads the active slice integer from the host view marker.
func (c *Counter) Current(hostView string) int {
	counter := filepath.Join(hostView, "slice_counter")
	data, err := os.ReadFile(counter)
	if err != nil {
		return 1
	}
	var g int
	_, _ = fmt.Sscanf(string(data), "%d", &g)
	if g < 1 {
		return 1
	}
	return g
}

// Bump writes the next slice counter to host and peer views.
func (c *Counter) Bump(hostView, peerView string, next int) error {
	payload := []byte(fmt.Sprintf("%d\n", next))
	for _, view := range []string{hostView, peerView} {
		if err := os.MkdirAll(view, 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(filepath.Join(view, "slice_counter"), payload, 0o644); err != nil {
			return err
		}
	}
	return nil
}

// SliceWidth returns the configured parallel width for a matrix row label.
func SliceWidth(row string) int {
	switch row {
	case "slice_once":
		return 1
	case "slice_twice", "recycle_trap", "warm_resume":
		return 2
	case "staggered_width":
		return 3
	default:
		return 1
	}
}
