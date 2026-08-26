package coord

import (
	"context"

	"vivostep.local/sim/pkg/api"
)

func awaitPrimary(ctx context.Context, primary <-chan struct{}, secondary <-chan struct{}) (api.PhaseToken, error) {
	select {
	case <-primary:
	case <-ctx.Done():
		return api.PhaseToken{}, ctx.Err()
	}
	select {
	case <-secondary:
	default:
	}
	if err := ctx.Err(); err != nil {
		return api.PhaseToken{}, err
	}
	return api.PhaseToken{Tick: 0}, nil
}

func JoinExported(ctx context.Context, roleDone <-chan struct{}, announceDone <-chan struct{}) (api.PhaseToken, error) {
	return awaitPrimary(ctx, roleDone, announceDone)
}
