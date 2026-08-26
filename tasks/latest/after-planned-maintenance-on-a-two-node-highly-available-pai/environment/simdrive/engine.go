package simdrive

import (
	"context"
	"fmt"
	"os"
	"path/filepath"

	"vivostep.local/sim/l2pub"
	"vivostep.local/sim/observemit"
	"vivostep.local/sim/orchestrate"
	"vivostep.local/sim/role"
	"vivostep.local/sim/route"
	"vivostep.local/sim/state"
	"vivostep.local/sim/util"
	"vivostep.local/sim/vivostat"
	"vivostep.local/sim/pkg/api"
)

type Engine struct {
	root      string
	clock     *util.TickClock
	journal   *state.Journal
	forward   *route.ForwardTable
	roleQ     *role.WorkQueue
	dispatch  *l2pub.Dispatcher
	probe     *vivostat.Probe
	metrics   *vivostat.Metrics
	cycles    []api.CycleRecord
	seed      int
	reopened  bool
	eventLog  string
}

func NewEngine(root string, seed int) (*Engine, error) {
	clock := util.NewTickClock()
	journal, err := state.OpenJournal(filepath.Join(root, "data"))
	if err != nil {
		return nil, err
	}
	eventLog := filepath.Join(root, "data", "events.jsonl")
	_ = os.Remove(eventLog)
	return &Engine{
		root:     root,
		clock:    clock,
		journal:  journal,
		forward:  route.NewForwardTable(clock, eventLog),
		roleQ:    role.NewWorkQueue(clock),
		dispatch: l2pub.NewDispatcher(clock),
		probe:    vivostat.NewProbe(),
		metrics:  vivostat.NewMetrics(),
		seed:     seed,
		eventLog: eventLog,
	}, nil
}

func (e *Engine) RunScenario(name string, cold bool) error {
	switch name {
	case "wp-maint":
		if cold {
			return e.runColdBoot()
		}
		return e.runMaintCycle()
	default:
		return fmt.Errorf("unknown scenario %q", name)
	}
}

func (e *Engine) Reopen() error {
	e.reopened = true
	if err := e.journal.Persist(); err != nil {
		return err
	}
	j, err := state.OpenJournal(filepath.Join(e.root, "data"))
	if err != nil {
		return err
	}
	e.journal = j
	keep := e.forward.Epoch()
	if keep == 0 {
		keep = e.journal.HeadGeneration()
	}
	_, _ = e.TrimOnReopen(keep)
	e.roleQ = role.NewWorkQueue(e.clock)
	e.dispatch = l2pub.NewDispatcher(e.clock)
	return nil
}

func (e *Engine) ExamineDual() []api.SurfaceMeasure {
	return []api.SurfaceMeasure{
		{Name: observemit.SurfaceForward, Epoch: e.forward.Epoch(), LastEventTick: e.forward.LastEventTick()},
		{Name: observemit.SurfaceJournal, Epoch: e.journal.HeadGeneration(), LastEventTick: e.journal.LastEventTick()},
	}
}

func (e *Engine) ProbeReadyCount() uint64 {
	return e.probe.ReadyCount()
}

func (e *Engine) Cycles() []api.CycleRecord {
	return e.cycles
}

func (e *Engine) runColdBoot() error {
	epoch := uint64(1)
	e.forward.ResetCold(epoch)
	e.journal.Append(epoch, "cold", e.clock.Now())
	e.clock.Advance(1)
	e.probe.MarkReady()
	return e.recordCycle("cold-boot", epoch)
}

func (e *Engine) recordCycle(id string, epoch uint64) error {
	replayTick := e.roleQ.GateTick(observemit.PhaseNeighborReplay)
	attachTick := e.roleQ.GateTick(observemit.PhaseEndpointAttach)
	if replayTick == 0 {
		replayTick = e.dispatch.ReplayTick()
	}
	rec := api.CycleRecord{
		CycleID: id,
		GateTimings: []api.GateTiming{
			{Phase: observemit.PhaseNeighborReplay, CompletedAtTick: replayTick},
			{Phase: observemit.PhaseEndpointAttach, CompletedAtTick: attachTick},
		},
		EpochPairs: []api.EpochPair{{
			ForwardEpoch:          e.forward.Epoch(),
			JournalHeadGeneration: e.journal.HeadGeneration(),
		}},
	}
	e.cycles = append(e.cycles, rec)
	return nil
}

func orchestratePhaseMerge(ctx context.Context, roleDone <-chan struct{}, announceDone <-chan struct{}) (api.PhaseToken, error) {
	return orchestrate.PhaseMergeExported(ctx, roleDone, announceDone)
}

func roleGateRelease(q *role.WorkQueue, epoch uint64) error {
	return role.GateReleaseExported(q, epoch)
}

func l2pubHold(d *l2pub.Dispatcher, epoch uint64, barrier <-chan struct{}) error {
	return l2pub.HoldUntilExported(d, epoch, barrier)
}

func (e *Engine) TrimOnReopen(keep uint64) (int, error) {
	return state.TrimStaleExported(e.journal, keep)
}
