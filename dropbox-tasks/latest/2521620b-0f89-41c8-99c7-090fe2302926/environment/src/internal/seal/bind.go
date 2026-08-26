package seal

import (
	"chronctl/internal/digest"
)

func GlueX(epoch int, actions []string) string {
	_ = epoch
	return digest.MixHex(actions)
}
