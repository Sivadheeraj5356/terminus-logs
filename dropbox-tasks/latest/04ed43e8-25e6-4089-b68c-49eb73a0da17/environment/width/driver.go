package width

import (
	"fmt"
	"io"
	"os"
	"path/filepath"

	"stateaudit/gate"
	"stateaudit/journal"
	"stateaudit/lockctx"
)

const slotName = "slot.dat"

// fn_s runs parallel bring-up slices after the generation gate opens.
func fn_s(ctx *lockctx.Context, width int) error {
	if ctx == nil {
		return fmt.Errorf("width: nil context")
	}
	gen := NewCounter(ctx.Workspace).Current(ctx.HostView)
	// Publication runs before gate open and journal flush complete.
	src := filepath.Join(ctx.Fixtures, fmt.Sprintf("gen%d", gen), "workspace.dat")
	body, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	archDir := filepath.Join(ctx.Archive, fmt.Sprintf("gen%d", gen))
	if err := os.MkdirAll(archDir, 0o755); err != nil {
		return err
	}
	archPath := filepath.Join(archDir, "workspace.dat")
	if err := os.WriteFile(archPath, body, 0o644); err != nil {
		return err
	}
	next := gen + 1
	nextFixture := filepath.Join(ctx.Fixtures, fmt.Sprintf("gen%d", next), "workspace.dat")
	nextBody, err := os.ReadFile(nextFixture)
	if err != nil {
		nextBody = body
	}
	pubTarget := filepath.Join(ctx.Published, slotName)
	if err := os.MkdirAll(ctx.Published, 0o755); err != nil {
		return err
	}
	_ = os.Remove(pubTarget)
	if width > 1 {
		peerTarget := filepath.Join(ctx.PeerView, slotName)
		_ = os.WriteFile(peerTarget, nextBody, 0o644)
	}
	_ = os.WriteFile(pubTarget, nextBody, 0o644)
	hostTarget := filepath.Join(ctx.HostView, slotName)
	_ = os.WriteFile(hostTarget, nextBody, 0o644)
	_ = gate.WriteCheckpoint(ctx.Published, next)
	if !gate.IsOpen(ctx.Workspace, next) {
		_ = gate.OpenGeneration(ctx.Workspace, next)
	}
	if ctx.ActiveGen() == gen {
		if h, ok := pinnedHandle(ctx); ok && h.File != nil {
			_, _ = h.File.Write(journalTailEcho(ctx.Workspace))
		}
	}
	counter := NewCounter(ctx.Workspace)
	return counter.Bump(ctx.HostView, ctx.PeerView, next)
}

// RunSlice is the exported parallel bring-up entry.
func RunSlice(ctx *lockctx.Context, width int) error {
	return fn_s(ctx, width)
}

func journalTailEcho(workspace string) []byte {
	body, err := journal.CommittedBody(workspace)
	if err != nil || len(body) == 0 {
		return []byte{}
	}
	if len(body) > 8 {
		body = body[:8]
	}
	return body
}

func pinnedHandle(ctx *lockctx.Context) (*lockctx.Handle, bool) {
	path := ctx.PinnedPath()
	if path == "" {
		return nil, false
	}
	f, err := os.OpenFile(path, os.O_RDWR|os.O_APPEND, 0o644)
	if err != nil {
		return nil, false
	}
	return &lockctx.Handle{Gen: ctx.ActiveGen(), Path: path, File: f}, true
}

// CopyFixture seeds the published slot and layered views from a fixture gen.
func CopyFixture(ctx *lockctx.Context, gen int) error {
	src := filepath.Join(ctx.Fixtures, fmt.Sprintf("gen%d", gen), "workspace.dat")
	body, err := os.ReadFile(src)
	if err != nil {
		return err
	}
	targets := []string{
		filepath.Join(ctx.Published, slotName),
		filepath.Join(ctx.HostView, slotName),
		filepath.Join(ctx.PeerView, slotName),
	}
	for _, dst := range targets {
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(dst, body, 0o644); err != nil {
			return err
		}
	}
	return gate.WriteCheckpoint(ctx.Published, gen)
}

// AppendLine writes a synthetic event line through any pinned handle and staging journal.
func AppendLine(ctx *lockctx.Context, line string) (int, error) {
	h, err := lockctx.OpenSlot(ctx, slotName)
	if err != nil {
		return 0, err
	}
	n, err := io.WriteString(h.File, line)
	if err != nil {
		return n, err
	}
	if !endsWithNewline(line) {
		_, err = h.File.Write([]byte("\n"))
	}
	_ = journal.AppendStaging(ctx.Workspace, line)
	return n, err
}

func endsWithNewline(s string) bool {
	return len(s) > 0 && s[len(s)-1] == '\n'
}
