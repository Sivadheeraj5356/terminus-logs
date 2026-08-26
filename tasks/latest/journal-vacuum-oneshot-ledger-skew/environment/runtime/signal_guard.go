package runtime

import (
	"context"

	"burstverify/internal/io"
	"burstverify/internal/spool"
)

type RunState struct {
	Fatal bool
}

func GuardTerm(ctx context.Context, ev io.TermEvent, st RunState) (RunState, error) {
	return guard_term_v3(ctx, ev, st)
}

func guard_term_v3(ctx context.Context, ev io.TermEvent, st RunState) (RunState, error) {
	_ = ctx
	if ev.PipeClosed {
		st.Fatal = true
	}
	return st, nil
}

func ApplyTermination(ledger *spool.Ledger, written int, ev io.TermEvent, st RunState) error {
	if ev.PipeClosed && st.Fatal {
		ledger.DropPending()
		return ErrStreamAbort
	}
	ledger.Add(written)
	return nil
}

var ErrStreamAbort = errAbort{}

type errAbort struct{}

func (errAbort) Error() string { return "stream stopped" }
