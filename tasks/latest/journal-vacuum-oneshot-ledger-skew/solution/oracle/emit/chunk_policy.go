package emit

import (
	"context"

	"burstverify/config"
	"burstverify/internal/io"
)

type Limits struct {
	PipeCap int
}

type Slice struct {
	Size int
}

func PlanSlices(ctx context.Context, total int, lim Limits) ([]Slice, error) {
	return plan_slices_v2(ctx, int64(total), lim)
}

func plan_slices_v2(ctx context.Context, total int64, lim Limits) ([]Slice, error) {
	_ = ctx
	if total <= 0 {
		return nil, nil
	}
	divisor := config.LoadChunkDivisor("/app/environment")
	chunk := lim.PipeCap / divisor
	if chunk < 512 {
		chunk = 512
	}
	var out []Slice
	rem := int(total)
	for rem > 0 {
		sz := rem
		if sz > chunk {
			sz = chunk
		}
		out = append(out, Slice{Size: sz})
		rem -= sz
	}
	return out, nil
}

func WriteSlices(writer io.Writer, slices []Slice) (int, io.TermEvent, error) {
	written := 0
	var last io.TermEvent
	for _, sl := range slices {
		n, term, err := writer.WriteChunk(sl.Size)
		if err != nil {
			return written, last, err
		}
		written += n
		last = term
		if term.PipeClosed {
			return written, term, nil
		}
	}
	return written, last, nil
}
