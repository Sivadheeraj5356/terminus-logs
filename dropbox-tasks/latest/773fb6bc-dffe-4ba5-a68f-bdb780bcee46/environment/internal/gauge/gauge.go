package gauge

import (
	"fmt"

	"github.com/lab/cvstack/internal/model"
)

func Text(v model.Vault) string {
	return fmt.Sprintf("gauge ok move=%d seal=%d mode=%s lanes=%d/%d foreign=%d",
		v.MoveGen, v.Seal, v.Mode, len(v.Slow), len(v.Fast), len(v.Foreign))
}
