package consumer

import (
	"streamkit/internal/config"
	"streamkit/pkg/pull"
)

func LaneGate(profile config.RuntimeProfile) *pull.Gate {
	return pull.NewGate(profile.LaneStride)
}
