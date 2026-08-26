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
	raw := fmt.Sprintf("%d:%s:%d", rev, tag, move)
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
