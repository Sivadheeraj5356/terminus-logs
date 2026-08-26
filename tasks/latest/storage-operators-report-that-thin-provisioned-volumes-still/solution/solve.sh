#!/bin/bash
set -euo pipefail
REPLAY_ROOT=/app/environment
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

apply_patch() {
  patch -p0 --forward --batch -d "$REPLAY_ROOT" -i "$ROOT_DIR/patches/$1"
}

apply_patch bind.patch
apply_patch range_align.patch
apply_patch range_ladder.patch
apply_patch catalog_fold.patch
apply_patch catalog_series.patch
apply_patch relay.patch

cat > "$REPLAY_ROOT/relay/emit_e.go" <<'EOF'
package relay

import "slotmgr/internal/store"

func emit_e(w store.Writer, batch store.Batch) (store.EmitStats, error) {
	mask := batch.SlotWidth
	if mask < 1 {
		mask = 4096
	}
	rec := store.TraceLine{Tick: batch.Offset / mask, AVal: batch.Len, BVal: batch.Len}
	if w != nil {
		_ = w.Record(rec)
	}
	return store.EmitStats{Forwarded: batch.Len, Skipped: 0}, nil
}

func RouteBatch(w store.Writer, batch store.Batch) (store.EmitStats, error) {
	return emit_e(w, batch)
}

type memWriter struct {
	rows []store.TraceLine
}

func (m *memWriter) Record(t store.TraceLine) error {
	m.rows = append(m.rows, t)
	return nil
}

func NewMemWriter() *memWriter {
	return &memWriter{}
}

func (m *memWriter) Rows() []store.TraceLine {
	return m.rows
}
EOF

apply_patch ledger.patch

python3 - <<'PY'
from pathlib import Path

path = Path("/app/environment/internal/pipeline/run.go")
text = path.read_text()

if '"slotmgr/internal/policy"' not in text:
    text = text.replace(
        '\t"slotmgr/internal/store"\n)',
        '\t"slotmgr/internal/policy"\n\t"slotmgr/internal/store"\n)',
    )

text = text.replace(
    """\tvar ratio store.UtilRatio
\tif err := loadJSON(filepath.Join(root, "fixtures", "util_ratio.json"), &ratio); err != nil {
\t\treturn err
\t}""",
    """\tratio, err := catalog.ResolveSeries(root)
\tif err != nil {
\t\treturn err
\t}""",
)

text = text.replace(
    "\t\taVal := slotRow.ClearedUnits",
    "\t\taVal := arraySnap.Rows[0].ClearedUnits",
)

text = text.replace(
    """\tslotsFree := volRow.SlotsFree
\tif len(viewDigests) > 0 {
\t\tslotsFree = viewDigests[0].SlotsFree
\t}
\tviews := make([]store.ViewRow, 0, len(peers))
\tfor i, peer := range peers {
\t\tpeerSlots := slotsFree
\t\tif i < len(viewDigests) {
\t\t\tpeerSlots = viewDigests[0].SlotsFree
\t\t}
\t\tviews = append(views, store.ViewRow{
\t\t\tPeerID: peer.PeerTag, BodyHex: body, Epoch: viewTick,
\t\t\tLaneTick: transcript[i].LaneTick, SeriesNum: ratio.SeriesNum, SeriesDen: ratio.SeriesDen,
\t\t\tSlotsFree: peerSlots, AppliedBytes: fwdApplied, SkippedBytes: fwdSkipped,
\t\t})
\t}""",
    """\tpol := policy.Load(root)
\tslotsFree := volRow.SlotsFree
\tif pol.ExportFirstDigestSlots && len(viewDigests) > 0 {
\t\tslotsFree = viewDigests[len(viewDigests)-1].SlotsFree
\t}
\tviews := make([]store.ViewRow, 0, len(peers))
\tfor i, peer := range peers {
\t\tpeerSlots := slotsFree
\t\tif pol.ExportFirstDigestSlots && len(viewDigests) > 0 {
\t\t\tpeerSlots = viewDigests[len(viewDigests)-1].SlotsFree
\t\t}
\t\tviews = append(views, store.ViewRow{
\t\t\tPeerID: peer.PeerTag, BodyHex: body, Epoch: viewTick,
\t\t\tLaneTick: transcript[i].LaneTick, SeriesNum: ratio.SeriesNum, SeriesDen: ratio.SeriesDen,
\t\t\tSlotsFree: peerSlots, AppliedBytes: fwdApplied, SkippedBytes: fwdSkipped,
\t\t})
\t}""",
)

needle = """\tif trim.ClearedUnits > 0 && viewTick <= trim.Tick {
\t\t\tviewTick = trim.Tick + 1
\t\t}
\t}
\tbody := bodyHex(prefix, viewTick)"""
replacement = """\tif trim.ClearedUnits > 0 && viewTick <= trim.Tick {
\t\t\tviewTick = trim.Tick + 1
\t\t}
\t}
\tif len(transcript) > 0 {
\t\tviewTick = transcript[len(transcript)-1].LaneTick
\t}
\tbody := bodyHex(prefix, viewTick)"""
if needle in text:
    text = text.replace(needle, replacement)

if "_ = bind.WriteSeq(root, cycle, viewTick)" in text and "ledger.WriteStaging" not in text:
    text = text.replace(
        "\t_ = bind.WriteSeq(root, cycle, viewTick)\n",
        "\t_ = bind.WriteSeq(root, cycle, viewTick)\n\t_ = ledger.WriteStaging(root, cycle, viewTick)\n",
    )
    text = text.replace(
        '\t"slotmgr/internal/policy"\n\t"slotmgr/internal/store"\n)',
        '\t"slotmgr/ledger"\n\t"slotmgr/internal/policy"\n\t"slotmgr/internal/store"\n)',
    )

text = text.replace("\tphase[0] = 1", "\tphase[0] = byte(cycle)")

text = text.replace(
    """\t\ttraceTick := laneTick
\t\tif !isArray && cycle >= 2 {
\t\t\ttraceTick = dig.Tick
\t\t}""",
    "\t\ttraceTick := laneTick",
)

path.write_text(text)
PY

python3 - <<'PY'
import re
from pathlib import Path
path = Path("/app/environment/ledger/fence_g.go")
text = path.read_text()
text = re.sub(
    r"func WriteStaging\(root string, cycle int, epoch int\) error \{.*?\n\}",
    """func WriteStaging(root string, cycle int, epoch int) error {
\treturn os.WriteFile(
\t\tfilepath.Join(root, "data", "staging.rev"),
\t\t[]byte(strconv.Itoa(epoch)),
\t\t0o644,
\t)
}""",
    text,
    count=1,
    flags=re.DOTALL,
)
path.write_text(text)
PY

cd "$REPLAY_ROOT"
export PATH="/usr/local/go/bin:$PATH"
go build -o /app/bin/volutil ./cmd/volutil
go build -o /app/bin/listctl ./cmd/listctl

bash /app/environment/scripts/repro_trim_cycle.sh
