#!/bin/bash
set -euo pipefail

export GOCACHE=/var/cache/cv-go
export GOMODCACHE=/var/cache/cv-gomod
export GOTOOLCHAIN=local
export PATH=/usr/local/go/bin:/usr/local/bin:${PATH:-/usr/bin:/bin}
mkdir -p "${GOCACHE}" "${GOMODCACHE}"
chmod 1777 "${GOCACHE}" "${GOMODCACHE}" 2>/dev/null || true

cd /app/environment

cat > harbor/quorum.go <<'EOF'
package harbor

import "github.com/lab/cvstack/internal/model"

func QuorumClosed(v model.Vault, alias model.Alias, active model.Ref) bool {
	post := v.RefPost
	if active.Path != post.Path || active.Rev < post.Rev {
		return false
	}
	if alias.Path != post.Path || alias.Rev < post.Rev {
		return false
	}
	if v.PtrPath != post.Path || v.PtrRev < post.Rev {
		return false
	}
	return true
}
EOF

cat > meridian/signal.go <<'EOF'
package meridian

import "github.com/lab/cvstack/internal/model"

func Open(v model.Vault, alias model.Alias) bool {
	if v.PtrRev < v.RefPost.Rev {
		return true
	}
	if v.PtrPath != v.RefPost.Path {
		return true
	}
	if v.RefPre.Path != v.RefPost.Path && alias.Path == v.RefPre.Path {
		return true
	}
	if alias.Rev < v.RefPost.Rev {
		return true
	}
	if v.Seal < v.MoveGen {
		return true
	}
	return false
}
EOF

python3 <<'PY'
from pathlib import Path
path = Path("horizon/frame.go")
text = path.read_text()
needle = "\tif alias.Rev < v.RefPost.Rev {\n\t\tlag = true\n\t}\n"
insert = needle + "\tif v.RefPre.Path != v.RefPost.Path && alias.Path == v.RefPre.Path {\n\t\tlag = true\n\t}\n"
if needle not in text:
    raise SystemExit("horizon alias rev block not found")
path.write_text(text.replace(needle, insert, 1))
PY

cat > anchor/apply.go <<'EOF'
package anchor

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/internal/vault"
)

func Seat(ws string, v *model.Vault) error {
	if v.MoveGen > 0 && v.RefPost.Rev > v.RefPre.Rev {
		v.PtrPath = v.RefPost.Path
		v.PtrRev = v.RefPost.Rev
		v.Seal = v.MoveGen
	}
	alias := model.Alias{Path: v.PtrPath, Rev: v.PtrRev}
	if err := vault.SaveAlias(ws, alias); err != nil {
		return err
	}
	active := model.Ref{
		Path:      v.PtrPath,
		Rev:       v.PtrRev,
		ActiveRow: v.RefPost.ActiveRow,
	}
	if err := vault.SaveActive(ws, active); err != nil {
		return err
	}
	return vault.Save(ws, *v)
}
EOF

cat > ribbon/policy.go <<'EOF'
package ribbon

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/laneio"
)

func OpenGate(v model.Vault) bool {
	if len(v.Dirty.Slots) == 0 {
		return true
	}
	if v.Dirty.Barrier < v.MoveGen {
		return true
	}
	if v.PtrRev >= v.RefPost.Rev {
		return true
	}
	return false
}

func SyncSlots(ws string, v model.Vault, open bool) error {
	if !open {
		return nil
	}
	if len(v.Dirty.Slots) == 0 {
		return nil
	}
	dirty := map[int]bool{}
	for _, s := range v.Dirty.Slots {
		dirty[s] = true
	}
	for _, row := range v.MapRows {
		if !dirty[row.A] {
			continue
		}
		fast, err := laneio.ReadFast(ws, row.B)
		if err != nil {
			continue
		}
		slow, err := laneio.ReadSlow(ws, row.A)
		if err != nil {
			continue
		}
		bind := fast.Bind
		if bind == 0 {
			bind = row.A
		}
		fast.Payload = slow.Payload
		fast.Epoch = slow.Epoch
		fast.Bind = bind
		fast.ID = row.B
		if err := laneio.WriteFast(ws, fast); err != nil {
			return err
		}
	}
	return nil
}

func Label(open bool, syncErr error, lagging bool) string {
	if open && syncErr == nil && !lagging {
		return "settled"
	}
	return "carry"
}
EOF

cat > pulse/counter.go <<'EOF'
package pulse

import "github.com/lab/cvstack/internal/model"

func Tick(v *model.Vault, g uint64, lagging bool) {
	if g > v.Tap.Gen {
		v.Tap.Gen = g
	}
	if lagging {
		return
	}
	if g >= v.MoveGen {
		v.Tap.Tally++
	}
}

func CommitTap(v *model.Vault, open bool, lagging bool) {
	if !open || lagging {
		return
	}
	if v.MoveGen > v.Tap.Gen {
		v.Tap.Gen = v.MoveGen
	}
	v.Tap.Tally++
}
EOF

cat > lens/route.go <<'EOF'
package lens

import (
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/laneio"
)

func Choose(ws string, slot int, v model.Vault, frame model.Frame) string {
	if frame.Lagging {
		p := laneio.FastPayload(ws, slot, v.MapRows)
		if p == "" {
			return laneio.SlowPayload(ws, slot)
		}
		return p
	}
	live := model.Live{
		Payload: laneio.SlowPayload(ws, slot),
		Epoch:   laneio.SlowEpoch(ws, slot),
		Slot:    slot,
	}
	if frame.Mode == "writethrough" {
		return live.Payload
	}
	cand := model.Candidate{
		Payload: laneio.FastPayload(ws, slot, v.MapRows),
		Epoch:   laneio.FastEpoch(ws, slot, v.MapRows),
		Slot:    slot,
	}
	if cand.Epoch < live.Epoch {
		return live.Payload
	}
	if cand.Epoch > live.Epoch {
		if cand.Payload != "" {
			return cand.Payload
		}
		return live.Payload
	}
	return live.Payload
}
EOF

cat > beacon/trace.go <<'EOF'
package beacon

import (
	"fmt"

	"github.com/lab/cvstack/internal/model"
)

func BindNote(row model.MapRow) string {
	return fmt.Sprintf("off=%d", row.Off)
}
EOF

cat > splice/table.go <<'EOF'
package splice

import "github.com/lab/cvstack/internal/model"

func Knit(src, dst []model.MapRow) []model.MapRow {
	bySlow := map[int]model.MapRow{}
	for _, r := range dst {
		bySlow[r.A] = r
	}
	out := make([]model.MapRow, 0, len(src))
	for _, r := range src {
		row := r
		if d, ok := bySlow[r.A]; ok {
			row.B = d.B
			row.Off = d.Off
		}
		out = append(out, row)
	}
	return out
}
EOF

cat > tablet/render.go <<'EOF'
package tablet

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"github.com/lab/cvstack/beacon"
	"github.com/lab/cvstack/internal/model"
	"github.com/lab/cvstack/laneio"
)

func hexTag(tag string, rev int, move uint64) string {
	raw := fmt.Sprintf("%s:%d:%d", tag, rev, move)
	sum := sha256.Sum256([]byte(raw))
	return hex.EncodeToString(sum[:])[:16]
}

func Ink(ws string, v model.Vault, tag string, prePath string) model.Record {
	traces := []model.TraceRow{}
	for _, row := range v.MapRows {
		traces = append(traces, model.TraceRow{
			Seq:  row.A,
			Kind: "bind",
			Slot: row.A,
			Note: beacon.BindNote(row),
			Rev:  v.PtrRev,
		})
	}
	clash := []model.ClashRow{}
	if v.RefPre.Rev != v.RefPost.Rev {
		clash = append(clash, model.ClashRow{
			Field: "ptr",
			Was:   fmt.Sprintf("%d", v.RefPre.Rev),
			Now:   fmt.Sprintf("%d", v.RefPost.Rev),
			Rev:   v.PtrRev,
		})
	}
	if prePath == v.RefPre.Path && v.RefPre.Path != v.RefPost.Path {
		clash = append(clash, model.ClashRow{
			Field: "origin",
			Was:   v.RefPre.Path,
			Now:   v.RefPost.Path,
			Rev:   v.PtrRev,
		})
	}
	tapRows := []model.TapRow{}
	if v.Tap.Tally > 0 && len(v.MapRows) > 0 {
		slot := v.MapRows[0].A
		tapRows = append(tapRows, model.TapRow{
			Seq:     1,
			Slot:    slot,
			Payload: laneio.SlowPayload(ws, slot),
			Tally:   v.Tap.Tally,
			Gen:     v.Tap.Gen,
		})
	}
	return model.Record{
		Traces: traces,
		Clash:  clash,
		Hash: model.HashView{
			Tag:    tag,
			Rev:    v.PtrRev,
			Fprint: hexTag(tag, v.PtrRev, v.MoveGen),
			Move:   v.MoveGen,
		},
		Tap:   tapRows,
		Gauge: fmt.Sprintf("gauge ok move=%d", v.MoveGen),
	}
}
EOF

python3 <<'PY'
from pathlib import Path
path = Path("internal/ops/ops.go")
text = path.read_text()
old = """func RunRead(ws string, eventsPath string) error {
	if err := ClearOutputs(ws); err != nil {
		return err
	}
	v, err := vault.Load(ws)
"""
new = """func RunRead(ws string, eventsPath string) error {
	v, err := vault.Load(ws)
"""
if old not in text:
    raise SystemExit("RunRead ClearOutputs block not found")
path.write_text(text.replace(old, new, 1))
PY

gofmt -w harbor/quorum.go meridian/signal.go horizon/frame.go anchor/apply.go \
	ribbon/policy.go pulse/counter.go lens/route.go beacon/trace.go \
	splice/table.go tablet/render.go internal/ops/ops.go

go build -o /tmp/cvctl ./cmd/cvctl
