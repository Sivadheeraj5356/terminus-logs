package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"stateaudit/emit"
	"stateaudit/gate"
	"stateaudit/health"
	"stateaudit/journal"
	"stateaudit/lockctx"
	"stateaudit/ready"
	"stateaudit/watch"
	"stateaudit/width"
)

func main() {
	tracePath := flag.String("trace", "/app/output/coordination_trace.json", "coordination trace output path")
	workspace := flag.String("workspace", "/app/data/workspace", "audit workspace root")
	fixtures := flag.String("fixtures", "/app/environment/fixtures/cycle", "cycle fixture root")
	flag.Parse()

	rows, err := LoadMatrix(*fixtures)
	if err != nil {
		fail(err)
	}
	ctx := lockctx.New(*workspace, *fixtures)
	out := make([]emit.Row, 0, len(rows))
	for _, row := range rows {
		record, err := runMatrixRow(ctx, row.Name)
		if err != nil {
			fail(fmt.Errorf("%s: %w", row.Name, err))
		}
		out = append(out, record)
	}
	if err := emit.WriteTrace(out, *tracePath, *workspace); err != nil {
		fail(err)
	}
}

func runMatrixRow(ctx *lockctx.Context, name string) (emit.Row, error) {
	ctx.Reset()
	if err := bootstrapWorkspace(ctx); err != nil {
		return emit.Row{}, err
	}
	switch name {
	case "slice_once":
		return driveSliceOnce(ctx)
	case "slice_twice":
		return driveSliceTwice(ctx)
	case "recycle_trap":
		return driveRecycleTrap(ctx)
	case "warm_resume":
		return driveWarmResume(ctx)
	case "staggered_width":
		return driveStaggeredWidth(ctx)
	default:
		return emit.Row{}, fmt.Errorf("unknown matrix row %q", name)
	}
}

func driveSliceOnce(ctx *lockctx.Context) (emit.Row, error) {
	gen := 1
	widthVal := width.SliceWidth("slice_once")
	if err := width.CopyFixture(ctx, gen); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=alpha seq=1"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, gen)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.RunSlice(ctx, widthVal); err != nil {
		return emit.Row{}, err
	}
	return buildRow(ctx, "slice_once", gen+1, gen)
}

func driveSliceTwice(ctx *lockctx.Context) (emit.Row, error) {
	gen := 1
	widthVal := width.SliceWidth("slice_twice")
	if err := width.CopyFixture(ctx, gen); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=cycle1-open"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, gen)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.RunSlice(ctx, widthVal); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=cycle2-open"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, 2)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.CopyFixture(ctx, 2); err != nil {
		return emit.Row{}, err
	}
	return buildRow(ctx, "slice_twice", 2, 1)
}

func driveRecycleTrap(ctx *lockctx.Context) (emit.Row, error) {
	gen := 1
	widthVal := width.SliceWidth("recycle_trap")
	if err := width.CopyFixture(ctx, gen); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=trap-open"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, gen)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.RunSlice(ctx, widthVal); err != nil {
		return emit.Row{}, err
	}
	ctx.Reset()
	_ = journal.Reset(ctx.Workspace)
	_ = gate.Reset(ctx.Workspace)
	if err := width.CopyFixture(ctx, 2); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=trap-reopen"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, 2)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.CopyFixture(ctx, 2); err != nil {
		return emit.Row{}, err
	}
	return buildRow(ctx, "recycle_trap", 2, 1)
}

func driveWarmResume(ctx *lockctx.Context) (emit.Row, error) {
	gen := 1
	widthVal := width.SliceWidth("warm_resume")
	if err := width.CopyFixture(ctx, gen); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=warm-start"); err != nil {
		return emit.Row{}, err
	}
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.RunSlice(ctx, widthVal); err != nil {
		return emit.Row{}, err
	}
	// Delayed symptom path: second append without full journal/gate coordination.
	if _, err := width.AppendLine(ctx, "evt=warm-resume"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, 2)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.CopyFixture(ctx, 2); err != nil {
		return emit.Row{}, err
	}
	return buildRow(ctx, "warm_resume", 2, gen)
}

func driveStaggeredWidth(ctx *lockctx.Context) (emit.Row, error) {
	gen := 1
	widthVal := width.SliceWidth("staggered_width")
	if err := width.CopyFixture(ctx, gen); err != nil {
		return emit.Row{}, err
	}
	if _, err := lockctx.OpenSlot(ctx, "slot.dat"); err != nil {
		return emit.Row{}, err
	}
	if _, err := width.AppendLine(ctx, "evt=stagger-open"); err != nil {
		return emit.Row{}, err
	}
	_ = journal.RecordFlush(ctx.Workspace)
	_ = gate.OpenGeneration(ctx.Workspace, gen)
	_ = watch.ApplyReload(ctx, widthVal)
	if err := width.RunSlice(ctx, widthVal); err != nil {
		return emit.Row{}, err
	}
	return buildRow(ctx, "staggered_width", 2, gen)
}

func buildRow(ctx *lockctx.Context, rowName string, gen int, parentGen int) (emit.Row, error) {
	hostBody, err := watch.HostViewBytes(ctx)
	if err != nil {
		hostBody = []byte{}
	}
	peerBody, err := watch.PeerViewBytes(ctx)
	if err != nil {
		peerBody = []byte{}
	}
	hostVisible := watch.HostVisibleBytes(ctx)
	peerNew := watch.PeerNewBytes(ctx)
	holdGap := hostVisible - peerNew
	stagingLag := journal.StagingLag(ctx.Workspace)
	checkpointEpoch := gate.CheckpointEpoch(ctx.Published)
	fixturePath := filepath.Join(ctx.Fixtures, fmt.Sprintf("gen%d", gen), "workspace.dat")
	fixtureBody, _ := os.ReadFile(fixturePath)
	journalBody, _ := journal.CommittedBody(ctx.Workspace)
	latchBody, _ := gate.LatchState(ctx.Workspace)
	stamp := emit.StampFor(gen, fixtureBody, journalBody)
	lineage := emit.LineageToken(parentGen, journalBody, latchBody)
	_ = health.PublishedSidecarCount(ctx.Published)
	_, _ = ready.ProbeListen("127.0.0.1:0")
	_, _ = watch.ReadPeerWindow(ctx, 4096)
	return emit.Row{
		Scenario:          rowName,
		SliceEpoch:        gen,
		MarkerFPHost:      emit.MarkerFP("host", hostBody),
		MarkerFPPeer:      emit.MarkerFP("peer", peerBody),
		HoldGap:           holdGap,
		StagingLag:        stagingLag,
		CheckpointEpoch:   checkpointEpoch,
		LineageToken:      lineage,
		PreservationStamp: stamp,
	}, nil
}

func bootstrapWorkspace(ctx *lockctx.Context) error {
	dirs := []string{
		ctx.Published,
		ctx.HostView,
		ctx.PeerView,
		filepath.Join(ctx.Archive, "gen1"),
		filepath.Join(ctx.Archive, "gen2"),
		filepath.Join(ctx.Archive, "gen3"),
	}
	for _, d := range dirs {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}
	_ = journal.Reset(ctx.Workspace)
	_ = gate.Reset(ctx.Workspace)
	counter := width.NewCounter(ctx.Workspace)
	return counter.Bump(ctx.HostView, ctx.PeerView, 1)
}

func fail(err error) {
	fmt.Fprintf(os.Stderr, "state-audit: %v\n", err)
	os.Exit(1)
}
