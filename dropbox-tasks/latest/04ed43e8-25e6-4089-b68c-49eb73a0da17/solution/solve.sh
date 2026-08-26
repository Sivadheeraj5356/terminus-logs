#!/bin/bash
set -euo pipefail

export PATH="/usr/bin:${PATH:-}"
export GOCACHE="${GOCACHE:-/tmp/gocache}"
export GOMODCACHE="${GOMODCACHE:-/tmp/gomodcache}"
install -d "${GOCACHE}" "${GOMODCACHE}" /app/bin /app/output /app/data/workspace

cd /app/environment

cat > journal/tail.go << 'EOF'
package journal

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"
)

func fn_j(workspace string) error {
	staging := filepath.Join(workspace, "journal", "staging.log")
	cursorPath := filepath.Join(workspace, "journal", "cursor")
	data, err := os.ReadFile(staging)
	if err != nil {
		return err
	}
	durable := filepath.Join(workspace, "journal", "committed.log")
	if err := os.MkdirAll(filepath.Dir(durable), 0o755); err != nil {
		return err
	}
	if err := os.WriteFile(durable, data, 0o644); err != nil {
		return err
	}
	cursor := len(data)
	return os.WriteFile(cursorPath, []byte(strconv.Itoa(cursor)), 0o644)
}

func AppendStaging(workspace, line string) error {
	dir := filepath.Join(workspace, "journal")
	if err := os.MkdirAll(dir, 0o755); err != nil {
		return err
	}
	staging := filepath.Join(dir, "staging.log")
	f, err := os.OpenFile(staging, os.O_CREATE|os.O_APPEND|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	if !strings.HasSuffix(line, "\n") {
		line += "\n"
	}
	_, err = f.WriteString(line)
	return err
}

func StagingLag(workspace string) int64 {
	staging := filepath.Join(workspace, "journal", "staging.log")
	cursorPath := filepath.Join(workspace, "journal", "cursor")
	body, err := os.ReadFile(staging)
	if err != nil {
		return 0
	}
	cursor := 0
	if raw, err := os.ReadFile(cursorPath); err == nil {
		cursor, _ = strconv.Atoi(strings.TrimSpace(string(raw)))
	}
	return int64(len(body) - cursor)
}

func CommittedBody(workspace string) ([]byte, error) {
	path := filepath.Join(workspace, "journal", "committed.log")
	return os.ReadFile(path)
}

func Reset(workspace string) error {
	dir := filepath.Join(workspace, "journal")
	_ = os.RemoveAll(dir)
	return os.MkdirAll(dir, 0o755)
}

func CursorPath(workspace string) string {
	return filepath.Join(workspace, "journal", "cursor")
}

func EnsureDir(workspace string) error {
	return os.MkdirAll(filepath.Join(workspace, "journal"), 0o755)
}

func RecordFlush(workspace string) error {
	return fn_j(workspace)
}

func FormatLag(workspace string) string {
	return fmt.Sprintf("lag=%d", StagingLag(workspace))
}
EOF

cat > gate/latch.go << 'EOF'
package gate

import (
	"fmt"
	"os"
	"path/filepath"
	"strconv"
	"strings"

	"stateaudit/journal"
)

func fn_g(workspace string, generation int) error {
	if generation < 1 {
		return fmt.Errorf("gate: invalid generation %d", generation)
	}
	if journal.StagingLag(workspace) > 0 {
		return fmt.Errorf("gate: staging lag %d", journal.StagingLag(workspace))
	}
	state := filepath.Join(workspace, "gate", "latch")
	if err := os.MkdirAll(filepath.Dir(state), 0o755); err != nil {
		return err
	}
	payload := []byte(fmt.Sprintf("open:%d\n", generation))
	return os.WriteFile(state, payload, 0o644)
}

func IsOpen(workspace string, generation int) bool {
	state := filepath.Join(workspace, "gate", "latch")
	raw, err := os.ReadFile(state)
	if err != nil {
		return false
	}
	want := fmt.Sprintf("open:%d", generation)
	return strings.TrimSpace(string(raw)) == want
}

func CheckpointEpoch(published string) int {
	path := filepath.Join(published, "checkpoint_epoch")
	raw, err := os.ReadFile(path)
	if err != nil {
		return 0
	}
	v, _ := strconv.Atoi(strings.TrimSpace(string(raw)))
	return v
}

func WriteCheckpoint(published string, generation int) error {
	if err := os.MkdirAll(published, 0o755); err != nil {
		return err
	}
	payload := []byte(fmt.Sprintf("%d\n", generation))
	return os.WriteFile(filepath.Join(published, "checkpoint_epoch"), payload, 0o644)
}

func Reset(workspace string) error {
	_ = os.RemoveAll(filepath.Join(workspace, "gate"))
	return os.MkdirAll(filepath.Join(workspace, "gate"), 0o755)
}

func OpenGeneration(workspace string, generation int) error {
	return fn_g(workspace, generation)
}

func LatchState(workspace string) ([]byte, error) {
	return os.ReadFile(filepath.Join(workspace, "gate", "latch"))
}
EOF

cat > lockctx/acquire.go << 'EOF'
package lockctx

import (
	"fmt"
	"os"
	"path/filepath"
)

const slotName = "slot.dat"

func fn_l(ctx *Context, slot string) (*Handle, error) {
	if ctx == nil {
		return nil, fmt.Errorf("lockctx: nil context")
	}
	target := filepath.Join(ctx.Published, slot)
	wantGen := readSliceCounter(ctx.HostView)
	ctx.mu.Lock()
	defer ctx.mu.Unlock()
	if ctx.active != nil && ctx.active.File != nil && ctx.active.Gen == wantGen {
		return ctx.active, nil
	}
	if ctx.active != nil && ctx.active.File != nil {
		_ = ctx.active.File.Close()
		ctx.active = nil
	}
	f, err := os.OpenFile(target, os.O_RDWR|os.O_APPEND|os.O_CREATE, 0o644)
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
EOF

cat > width/driver.go << 'EOF'
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

func fn_s(ctx *lockctx.Context, width int) error {
	if ctx == nil {
		return fmt.Errorf("width: nil context")
	}
	gen := NewCounter(ctx.Workspace).Current(ctx.HostView)
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
	if err := journal.RecordFlush(ctx.Workspace); err != nil {
		return err
	}
	if err := gate.OpenGeneration(ctx.Workspace, next); err != nil {
		return err
	}
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
	if err := os.WriteFile(pubTarget, nextBody, 0o644); err != nil {
		return err
	}
	hostTarget := filepath.Join(ctx.HostView, slotName)
	peerTarget := filepath.Join(ctx.PeerView, slotName)
	for _, dst := range []string{hostTarget, peerTarget} {
		if err := os.MkdirAll(filepath.Dir(dst), 0o755); err != nil {
			return err
		}
		if err := os.WriteFile(dst, nextBody, 0o644); err != nil {
			return err
		}
	}
	_ = gate.WriteCheckpoint(ctx.Published, next)
	counter := NewCounter(ctx.Workspace)
	return counter.Bump(ctx.HostView, ctx.PeerView, next)
}

func RunSlice(ctx *lockctx.Context, width int) error {
	return fn_s(ctx, width)
}

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
EOF

cat > watch/reload.go << 'EOF'
package watch

import (
	"fmt"
	"os"
	"path/filepath"

	"stateaudit/gate"
	"stateaudit/lockctx"
)

const slotName = "slot.dat"

func fn_m(ctx *lockctx.Context, batch int) error {
	if ctx == nil {
		return fmt.Errorf("watch: nil context")
	}
	if batch < 1 {
		return nil
	}
	gen := activeSliceCounter(ctx.HostView)
	if !gate.IsOpen(ctx.Workspace, gen) {
		return nil
	}
	merged := filepath.Join(ctx.Published, slotName)
	data, err := os.ReadFile(merged)
	if err != nil {
		return err
	}
	peer := filepath.Join(ctx.PeerView, slotName)
	return os.WriteFile(peer, data, 0o644)
}

func ApplyReload(ctx *lockctx.Context, batch int) error {
	return fn_m(ctx, batch)
}

func PeerNewBytes(ctx *lockctx.Context) int64 {
	if ctx == nil {
		return 0
	}
	peerPath := filepath.Join(ctx.PeerView, slotName)
	data, err := os.ReadFile(peerPath)
	if err != nil {
		return 0
	}
	return int64(len(data))
}

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

func HostViewBytes(ctx *lockctx.Context) ([]byte, error) {
	p := filepath.Join(ctx.HostView, slotName)
	return os.ReadFile(p)
}

func PeerViewBytes(ctx *lockctx.Context) ([]byte, error) {
	p := filepath.Join(ctx.PeerView, slotName)
	return os.ReadFile(p)
}

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
EOF

cat > emit/writer.go << 'EOF'
package emit

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

func fn_e(rows []Row, outPath, workspace string) error {
	env := Envelope{Runs: rows}
	for i := range env.Runs {
		env.Runs[i].RowSeal = sealRow(env.Runs[i])
	}
	sort.Slice(env.Runs, func(i, j int) bool {
		return env.Runs[i].Scenario < env.Runs[j].Scenario
	})
	env.ReportDigest = digestEnvelope(env.Runs)
	env.ReplayToken = replayToken(env.ReportDigest, workspace)
	data, err := json.MarshalIndent(env, "", "  ")
	if err != nil {
		return err
	}
	if err := os.MkdirAll(filepath.Dir(outPath), 0o755); err != nil {
		return err
	}
	return os.WriteFile(outPath, append(data, '\n'), 0o644)
}

func WriteTrace(rows []Row, outPath, workspace string) error {
	return fn_e(rows, outPath, workspace)
}

func MarkerFP(label string, body []byte) string {
	h := sha256.Sum256([]byte(label + "|" + string(body)))
	return hex.EncodeToString(h[:])[:16]
}

func StampFor(gen int, fixtureBody []byte, _ []byte) string {
	payload := fmt.Sprintf("%d|", gen)
	h := sha256.Sum256(append([]byte(payload), fixtureBody...))
	return hex.EncodeToString(h[:])[:16]
}

func LineageToken(parentGen int, journalBody, latchBody []byte) string {
	payload := fmt.Sprintf("%d|", parentGen)
	h := sha256.Sum256(append(append([]byte(payload), journalBody...), latchBody...))
	return hex.EncodeToString(h[:])[:16]
}

func sealRow(row Row) string {
	parts := []string{
		row.Scenario,
		fmt.Sprintf("%d", row.SliceEpoch),
		row.MarkerFPHost,
		row.MarkerFPPeer,
		fmt.Sprintf("%d", row.HoldGap),
		fmt.Sprintf("%d", row.StagingLag),
		fmt.Sprintf("%d", row.CheckpointEpoch),
		row.LineageToken,
		row.PreservationStamp,
	}
	h := sha256.Sum256([]byte(strings.Join(parts, "|")))
	return hex.EncodeToString(h[:])[:16]
}

func digestEnvelope(rows []Row) string {
	var parts []string
	for _, row := range rows {
		parts = append(parts, strings.Join([]string{
			row.Scenario,
			fmt.Sprintf("%d", row.SliceEpoch),
			row.MarkerFPHost,
			row.MarkerFPPeer,
			fmt.Sprintf("%d", row.HoldGap),
			fmt.Sprintf("%d", row.StagingLag),
			fmt.Sprintf("%d", row.CheckpointEpoch),
			row.LineageToken,
			row.PreservationStamp,
			row.RowSeal,
		}, ";"))
	}
	sort.Strings(parts)
	h := sha256.Sum256([]byte(strings.Join(parts, "\n")))
	return hex.EncodeToString(h[:])[:16]
}

func replayToken(reportDigest, workspace string) string {
	h := sha256.Sum256([]byte(reportDigest + "|" + workspace))
	return hex.EncodeToString(h[:])[:16]
}
EOF

go build -o /app/bin/state-audit ./driver/
/app/bin/state-audit \
  --trace /app/output/coordination_trace.json \
  --workspace /app/data/workspace \
  --fixtures /app/environment/fixtures/cycle

echo "state-audit oracle complete"
