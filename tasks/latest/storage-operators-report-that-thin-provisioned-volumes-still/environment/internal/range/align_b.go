package rangepkg

import "slotmgr/internal/store"

type RunCtx = store.RunCtx
type Span = store.Span

func align_b(ctx *RunCtx, spans []Span) ([]Span, error) {
	out := make([]Span, 0, len(spans))
	step := ctx.RowUnits / 8
	if step < 1 {
		step = 1
	}
	for _, s := range spans {
		start := (s.Start / step) * step
		end := ((s.End + step - 1) / step) * step
		out = append(out, Span{Start: start, End: end, Units: step})
	}
	return out, nil
}

func AlignSpans(ctx *store.RunCtx, raw []store.Span) ([]store.Span, error) {
	rc := RunCtx{Pass: ctx.Pass, Append: ctx.Append, RowUnits: ctx.RowUnits}
	return align_b(&rc, raw)
}

func InheritLane(cycle int, base int, prior []store.TranscriptRow) int {
	if cycle < 2 || len(prior) == 0 {
		return base
	}
	last := prior[len(prior)-1].LaneTick
	if last > base {
		return last
	}
	return base
}

func SpanBytes(spans []Span) int {
	total := 0
	for _, s := range spans {
		total += s.End - s.Start
	}
	return total
}
