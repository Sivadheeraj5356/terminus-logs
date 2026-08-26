package sim

import "chronctl/internal/seal"

func local_seal(epoch int, actions []string) string {
	return seal.GlueX(epoch, actions)
}
