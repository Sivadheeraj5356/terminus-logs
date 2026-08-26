package orchestrate

import (
	"context"

	"vivostep.local/sim/coord"
	"vivostep.local/sim/pkg/api"
)

func PhaseMergeExported(ctx context.Context, roleDone <-chan struct{}, announceDone <-chan struct{}) (api.PhaseToken, error) {
	return coord.JoinExported(ctx, roleDone, announceDone)
}
