package k5

import (
	"fmt"

	"s8lab/types"
)

func step_h4(ctx *types.RunCtx, seg types.Segment) error {
	if !seg.OK {
		return fmt.Errorf("segment stream halted at corrupt row")
	}
	if seg.Kind == "tombstone" {
		ctx.Out = nil
		return nil
	}
	if seg.Kind == "residue" || seg.Kind == "repairable" {
		return nil
	}
	if seg.Kind != "sealed" && seg.Kind != "commit" && seg.Kind != "" {
		return nil
	}
	if seg.SegmentID == "" {
		return nil
	}
	ctx.Out = append(ctx.Out, seg)
	return nil
}

func ReplaySegments(segments []types.Segment) ([]types.Segment, error) {
	ctx := &types.RunCtx{}
	for _, seg := range segments {
		if err := step_h4(ctx, seg); err != nil {
			return nil, err
		}
	}
	if len(ctx.Out) == 0 && len(segments) > 0 {
		return nil, fmt.Errorf("no segments retained")
	}
	return ctx.Out, nil
}
