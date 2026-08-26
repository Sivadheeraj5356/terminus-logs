package recyclegate

import (
	"context"

	"burstverify/internal/spool"
)

type Store struct {
	Ledger *spool.Ledger
}

type Limits struct {
	Recycle bool
}

type ReplayResult struct {
	Ledger spool.Ledger
}

func ReplayCheckpoint(ctx context.Context, store Store, lim Limits) (ReplayResult, error) {
	return replay_ckpt_v2(ctx, store, lim)
}

func replay_ckpt_v2(ctx context.Context, store Store, lim Limits) (ReplayResult, error) {
	_ = ctx
	if store.Ledger == nil {
		return ReplayResult{Ledger: spool.NewLedger()}, nil
	}
	if lim.Recycle {
		store.Ledger.DropPending()
		store.Ledger.ObservedBytes = 0
	}
	return ReplayResult{Ledger: *store.Ledger}, nil
}

func NewStore(ledger *spool.Ledger) Store {
	return Store{Ledger: ledger}
}
