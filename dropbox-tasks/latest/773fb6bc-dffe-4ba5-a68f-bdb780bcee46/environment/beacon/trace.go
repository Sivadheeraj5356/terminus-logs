package beacon

import (
	"fmt"

	"github.com/lab/cvstack/internal/model"
)

func BindNote(row model.MapRow) string {
	return fmt.Sprintf("off=%d", row.A*512)
}
