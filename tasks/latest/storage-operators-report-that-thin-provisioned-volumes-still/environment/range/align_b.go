package rangepkg

import (
	"slotmgr/internal/policy"
	"slotmgr/internal/store"
)

type RunCtx = store.RunCtx
type Span = store.Span

func laneBase(cycle int, base int, prior []store.TranscriptRow, root string) int {
	pol := policy.Load(root)
	if cycle < 2 || len(prior) == 0 {
		return base
	}
	if !pol.InheritUsePriorLane {
		return base
	}
	first := prior[0].LaneTick
	if first > base {
		return first
	}
	return base
}

func align_b(ctx *RunCtx, spans []Span, root string) ([]Span, error) {
	pol := policy.Load(root)
	out := make([]Span, 0, len(spans))
	step := ctx.RowUnits
	if step < 1 {
		step = 4096
	}
	for _, s := range spans {
		start := (s.Start / step) * step
		end := ((s.End + step - 1) / step) * step
		units := step
		if pol.AlignPreserveFixtureAppend && ctx.Append && s.Units > 0 {
			units = s.Units
		}
		out = append(out, Span{Start: start, End: end, Units: units})
	}
	return out, nil
}

func AlignSpans(ctx *store.RunCtx, raw []store.Span, root string) ([]store.Span, error) {
	rc := RunCtx{Pass: ctx.Pass, Append: ctx.Append, RowUnits: ctx.RowUnits}
	return align_b(&rc, raw, root)
}

func InheritLane(cycle int, base int, prior []store.TranscriptRow, root string) int {
	return laneBase(cycle, base, prior, root)
}

func SpanBytes(spans []Span) int {
	total := 0
	for _, s := range spans {
		total += s.End - s.Start
	}
	return total
}
