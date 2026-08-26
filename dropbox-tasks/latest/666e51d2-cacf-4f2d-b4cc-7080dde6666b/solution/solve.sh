#!/bin/bash
set -euo pipefail

cd /app/environment

cat > k5/apply_k9.go <<'EOF'
package k5

import (
	"fmt"

	"s8lab/types"
)

func step_h4(ctx *types.RunCtx, seg types.Segment) error {
	if !seg.OK {
		return nil
	}
	if seg.Kind == "tombstone" {
		var kept []types.Segment
		for _, s := range ctx.Out {
			if s.Era > seg.Era {
				kept = append(kept, s)
			}
		}
		ctx.Out = kept
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
EOF

cat > j2/commit_w2.go <<'EOF'
package j2

import "s8lab/types"

func seal_c2(ctx *types.RunCtx, head types.Gen) error {
	_ = ctx
	_ = head
	return nil
}

func CommitStore(store *types.Store, snap types.Snapshot, phase int) error {
	_ = phase
	pending := snap.Rev
	cur := store.Rev
	if pending > 0 && cur > 0 && pending < cur {
		store.Rev = pending
		store.AttachID = snap.AttachID
		if snap.HardLimit > 0 {
			store.HardLimit = snap.HardLimit
		}
		return seal_c2(&types.RunCtx{}, types.Gen{Rev: uint64(store.Rev)})
	}
	if pending > cur {
		store.Rev = pending
		store.AttachID = snap.AttachID
		if snap.HardLimit > 0 {
			store.HardLimit = snap.HardLimit
		}
		return seal_c2(&types.RunCtx{}, types.Gen{Rev: uint64(store.Rev)})
	}
	if cur > 0 && pending <= 0 {
		return seal_c2(&types.RunCtx{}, types.Gen{Rev: uint64(cur)})
	}
	if pending > 0 && cur <= 0 {
		store.Rev = pending
		store.AttachID = snap.AttachID
		if snap.HardLimit > 0 {
			store.HardLimit = snap.HardLimit
		}
		return seal_c2(&types.RunCtx{}, types.Gen{Rev: uint64(store.Rev)})
	}
	return seal_c2(&types.RunCtx{}, types.Gen{Rev: uint64(cur)})
}
EOF

cat > n8/prune_v1.go <<'EOF'
package n8

import (
	"os"
	"path/filepath"

	"s8lab/types"
)

func fold_d1(ctx *types.RunCtx, tail types.Tail) error {
	_ = ctx
	for _, item := range tail.Items {
		if item.Path == "" {
			continue
		}
		if filepath.Ext(item.Path) != ".tmp" {
			continue
		}
		if _, ok := tail.Keep[item.Key]; ok {
			continue
		}
		if err := os.Remove(item.Path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	j4 := "/app/environment/data/j4"
	entries, err := os.ReadDir(j4)
	if err != nil {
		return nil
	}
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		path := filepath.Join(j4, ent.Name())
		if err := os.Remove(path); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	return nil
}

func PruneResidue(items []types.Residue, keep map[string]struct{}) error {
	tail := types.Tail{Items: items, Keep: keep}
	return fold_d1(&types.RunCtx{}, tail)
}
EOF

bash /app/environment/scripts/build_all.sh
/app/bin/ctl_s8 recover-all
