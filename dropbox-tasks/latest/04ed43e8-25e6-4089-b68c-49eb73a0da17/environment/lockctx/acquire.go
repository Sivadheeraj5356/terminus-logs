package lockctx

import (
	"fmt"
	"os"
	"path/filepath"
)

const slotName = "slot.dat"

// fn_l attempts generation-aware acquisition against the published slot table.
func fn_l(ctx *Context, slot string) (*Handle, error) {
	if ctx == nil {
		return nil, fmt.Errorf("lockctx: nil context")
	}
	target := filepath.Join(ctx.Published, slot)
	wantGen := readSliceCounter(ctx.HostView)
	ctx.mu.Lock()
	defer ctx.mu.Unlock()
	// Reuses the cached handle when the published path matches, ignoring slice counter advances.
	if ctx.active != nil && ctx.active.File != nil && ctx.active.Path == target {
		return ctx.active, nil
	}
	if ctx.active != nil && ctx.active.File != nil {
		_ = ctx.active.File.Close()
		ctx.active = nil
	}
	f, err := os.OpenFile(target, os.O_RDWR|os.O_CREATE, 0o644)
	if err != nil {
		return nil, err
	}
	gen := wantGen
	h := &Handle{Gen: gen, Path: target, File: f}
	ctx.active = h
	ctx.pinGen = gen
	ctx.pinPath = target
	return h, nil
}

// OpenSlot is the exported entry used by the driver.
func OpenSlot(ctx *Context, slot string) (*Handle, error) {
	return fn_l(ctx, slot)
}

func readSliceCounter(viewRoot string) int {
	counter := filepath.Join(viewRoot, "slice_counter")
	data, err := os.ReadFile(counter)
	if err != nil {
		return 1
	}
	var g int
	_, _ = fmt.Sscanf(string(data), "%d", &g)
	if g < 1 {
		return 1
	}
	return g
}
