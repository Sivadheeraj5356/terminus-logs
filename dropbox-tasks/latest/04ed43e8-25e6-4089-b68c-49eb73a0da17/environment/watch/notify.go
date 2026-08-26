package watch

import (
	"os"
	"path/filepath"

	"stateaudit/lockctx"
)

// NotifyReady records a reload notification timestamp for diagnostics.
func NotifyReady(ctx *lockctx.Context) error {
	if ctx == nil {
		return os.ErrInvalid
	}
	stamp := filepath.Join(ctx.Workspace, "reload.notify")
	return os.WriteFile(stamp, []byte("1\n"), 0o644)
}

// ReadPeerWindow returns peer view bytes for audit sampling.
func ReadPeerWindow(ctx *lockctx.Context, window int) ([]byte, error) {
	_ = window
	p := filepath.Join(ctx.PeerView, slotName)
	return os.ReadFile(p)
}
