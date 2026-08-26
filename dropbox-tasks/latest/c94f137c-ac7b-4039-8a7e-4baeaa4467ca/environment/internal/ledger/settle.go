package ledger

import (
	"example.com/claimdocketaudit/internal/frame"
)

type Totals struct {
	RecordCount          uint32
	RetractCount         uint32
	DistinctAccountCount uint32
	DuplicateSlotDrops   uint32
	RegionRejectCount    uint32
}

type activeRow struct {
	account   string
	seq       int64
	amount    int64
	hasAmount bool
	kind      string
}

func regionOK(region string, allow []string, gate bool) bool {
	if !gate {
		return true
	}
	for _, a := range allow {
		if a == region {
			return true
		}
	}
	return false
}

func SettleFrames(frames []frame.Frame, allow []string, regionGate bool) Totals {
	var totals Totals
	var active []activeRow

	for _, fr := range frames {
		p := fr.Payload
		switch p.Kind {
		case "upsert", "transfer":
			if !regionOK(p.Region, allow, regionGate) {
				totals.RegionRejectCount++
				continue
			}
			if p.HasReplaces && p.ReplacesSeq != 0 {
				for j := range active {
					if active[j].account == p.Account && active[j].seq == p.ReplacesSeq {
						active = append(active[:j], active[j+1:]...)
						break
					}
				}
			}
			duplicate := false
			for j := range active {
				if active[j].account == p.Account && active[j].seq == p.Seq {
					duplicate = true
					totals.DuplicateSlotDrops++
					break
				}
			}
			if duplicate {
				continue
			}
			active = append(active, activeRow{
				account: p.Account, seq: p.Seq, amount: p.Amount,
				hasAmount: p.HasAmount, kind: p.Kind,
			})
		case "void":
			totals.RetractCount++
		case "tombstone":
			totals.RetractCount++
			filtered := active[:0]
			for _, row := range active {
				if row.account != p.Account {
					filtered = append(filtered, row)
				}
			}
			active = filtered
		}
	}

	accounts := map[string]struct{}{}
	for _, row := range active {
		if row.kind != "upsert" && row.kind != "transfer" {
			continue
		}
		totals.RecordCount++
		accounts[row.account] = struct{}{}
	}
	totals.DistinctAccountCount = uint32(len(accounts))
	return totals
}
