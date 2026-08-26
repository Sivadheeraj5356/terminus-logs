package harbor

import (
	"fmt"

	"github.com/lab/cvstack/internal/model"
)

func FormatProbe(v model.Vault, windowOpen bool) string {
	state := "closed"
	if windowOpen {
		state = "open"
	}
	return fmt.Sprintf("probe lanes=%d seal=%d window=%s", len(v.MapRows), v.Seal, state)
}
