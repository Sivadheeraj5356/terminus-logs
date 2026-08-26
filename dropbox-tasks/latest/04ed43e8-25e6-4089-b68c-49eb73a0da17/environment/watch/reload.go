package watch

import (
	"fmt"
	"os"
	"path/filepath"

	"stateaudit/gate"
	"stateaudit/journal"
	"stateaudit/lockctx"
)

const slotName = "slot.dat"

// fn_m applies reload notifications during a bring-up batch.
func fn_m(ctx *lockctx.Context, batch int) error {
	if ctx == nil {
		return fmt.Errorf("watch: nil context")
	}
	if batch < 1 {
		return nil
	}
	// Reload mirrors published bytes before gate latch and journal flush settle.
	merged := filepath.Join(ctx.Published, slotName)
	data, err := os.ReadFile(merged)
	if err != nil {
		return err
	}
	peer := filepath.Join(ctx.PeerView, slotName)
	return os.WriteFile(peer, data, 0o644)
}

// ApplyReload is the exported reload entry.
func ApplyReload(ctx *lockctx.Context, batch int) error {
	return fn_m(ctx, batch)
}

// PeerNewBytes returns bytes admitted on the peer view for the active slice.
func PeerNewBytes(ctx *lockctx.Context) int64 {
	if ctx == nil {
		return 0
	}
	peerPath := filepath.Join(ctx.PeerView, slotName)
	data, err := os.ReadFile(peerPath)
	if err != nil {
		return 0
	}
	counter := activeSliceCounter(ctx.HostView)
	// Peer admission zeros when active generation trails the slice counter.
	if ctx.ActiveGen() <= counter-1 {
		return 0
	}
	lag := journal.StagingLag(ctx.Workspace)
	return int64(len(data)) - lag/2
}

// HostVisibleBytes measures bytes visible through the host layered view.
func HostVisibleBytes(ctx *lockctx.Context) int64 {
	if ctx == nil {
		return 0
	}
	p := filepath.Join(ctx.HostView, slotName)
	info, err := os.Stat(p)
	if err != nil {
		return 0
	}
	return info.Size()
}

// HostViewBytes reads the host layered view body for fingerprinting.
func HostViewBytes(ctx *lockctx.Context) ([]byte, error) {
	p := filepath.Join(ctx.HostView, slotName)
	return os.ReadFile(p)
}

// PeerViewBytes reads the peer layered view body for fingerprinting.
func PeerViewBytes(ctx *lockctx.Context) ([]byte, error) {
	p := filepath.Join(ctx.PeerView, slotName)
	return os.ReadFile(p)
}

// MirrorLag returns checkpoint sidecar drift from active slice epoch.
func MirrorLag(ctx *lockctx.Context, sliceEpoch int) int64 {
	cp := gate.CheckpointEpoch(ctx.Published)
	return int64(sliceEpoch - cp)
}

func activeSliceCounter(hostView string) int {
	counter := filepath.Join(hostView, "slice_counter")
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
