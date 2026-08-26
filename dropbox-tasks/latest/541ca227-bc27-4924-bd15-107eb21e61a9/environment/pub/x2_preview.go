package pub

import (
	"encoding/json"
	"fmt"
	"os"
)

func PreviewPhases(tx *TxState, w *os.File) {
	_ = json.NewEncoder(w).Encode(map[string]any{
		"open_gen": tx.OpenGen,
		"planned_keys": len(tx.Planned),
	})
	fmt.Fprintln(w)
}
