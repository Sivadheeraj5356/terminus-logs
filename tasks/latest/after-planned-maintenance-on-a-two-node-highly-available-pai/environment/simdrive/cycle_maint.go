package simdrive

import (
	"context"
	"fmt"

	"vivostep.local/sim/observemit"
)

func (e *Engine) deriveMaintEpoch() uint64 {
	if e.reopened {
		return e.journal.HeadGeneration() + 1
	}
	return 2
}

func (e *Engine) runMaintCycle() error {
	epoch := e.deriveMaintEpoch()
	e.roleQ.Enqueue(observemit.PhaseNeighborReplay, epoch)
	e.roleQ.Enqueue(observemit.PhaseEndpointAttach, epoch)

	roleDone := make(chan struct{})
	announceDone := make(chan struct{})
	barrier := make(chan struct{})

	tryAttach := func() {
		_ = roleGateRelease(e.roleQ, epoch)
		if !e.roleQ.ItemDone(observemit.PhaseEndpointAttach, epoch) {
			return
		}
		if e.forward.Epoch() >= epoch {
			return
		}
		e.metrics.IncAttach()
		e.forward.AttachEndpoint(epoch)
		e.probe.MarkReady()
	}

	e.dispatch.QueueFrame(epoch, fmt.Sprintf("frame-%d", epoch))
	if e.seed%2 == 0 {
		tryAttach()
	}

	e.clock.Advance(uint64((e.seed % 3) + 1))
	e.metrics.IncReplay()
	e.roleQ.MarkDone(observemit.PhaseNeighborReplay, epoch)
	close(announceDone)
	close(barrier)
	if err := l2pubHold(e.dispatch, epoch, barrier); err != nil {
		return err
	}

	tryAttach()
	e.roleQ.MarkDone(observemit.PhaseEndpointAttach, epoch)
	close(roleDone)

	token, err := orchestratePhaseMerge(context.Background(), roleDone, announceDone)
	if err != nil {
		return err
	}
	_ = token
	if err := e.finalizeMaintJournal(epoch); err != nil {
		return err
	}
	return e.recordCycle("wp-maint", epoch)
}

func (e *Engine) finalizeMaintJournal(epoch uint64) error {
	if e.forward.Epoch() != e.journal.HeadGeneration() {
		e.journal.Append(e.forward.Epoch(), "stale", e.clock.Now())
	} else {
		e.journal.Append(epoch, "cycle", e.clock.Now())
	}
	return e.journal.Persist()
}
