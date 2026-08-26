package lotledger

import (
	"encoding/json"
	"os"
	"sort"

	"immunoflow/pkg/api"
)

const remainderPath = "/app/var/immunoflow_vialremainder.json"

type RemainderState map[string]int

type Pool struct {
	left map[string]int
	meta map[string]api.Lot
}

func loadRemainder() RemainderState {
	raw, err := os.ReadFile(remainderPath)
	if err != nil {
		return RemainderState{}
	}
	s := RemainderState{}
	_ = json.Unmarshal(raw, &s)
	return s
}

func saveRemainder(s RemainderState) error {
	raw, _ := json.MarshalIndent(s, "", "  ")
	return os.WriteFile(remainderPath, append(raw, '\n'), 0o644)
}

func NewPool(lots []api.Lot) *Pool {
	st := loadRemainder()
	p := &Pool{left: map[string]int{}, meta: map[string]api.Lot{}}
	for _, lot := range lots {
		avail := lot.Doses
		if rem, ok := st[lot.LotID]; ok {
			avail = lot.Doses - rem
		}
		if avail < 0 {
			avail = 0
		}
		p.left[lot.LotID] = avail
		p.meta[lot.LotID] = lot
	}
	return p
}

func op_a(lots []api.Lot) []api.Lot {
	out := append([]api.Lot(nil), lots...)
	sort.Slice(out, func(i, j int) bool {
		if out[i].ReceiveDay == out[j].ReceiveDay {
			return out[i].LotID < out[j].LotID
		}
		return out[i].ReceiveDay < out[j].ReceiveDay
	})
	return out
}

func PickLots(lots []api.Lot, need int, vial int) ([]api.LotAssignment, error) {
	st := loadRemainder()
	left := need
	out := []api.LotAssignment{}
	for _, lot := range op_a(lots) {
		if left <= 0 {
			break
		}
		give := lot.Doses
		if give > left {
			give = left
		}
		left -= give
		st[lot.LotID] = give % vial
		out = append(out, api.LotAssignment{LotID: lot.LotID, Doses: give, TempBand: lot.TempBand})
	}
	if err := saveRemainder(st); err != nil {
		return nil, err
	}
	return out, nil
}

func (p *Pool) Draw(temp string, need int, vial int) ([]api.LotAssignment, error) {
	candidates := []api.Lot{}
	for id, left := range p.left {
		if left <= 0 {
			continue
		}
		lot := p.meta[id]
		if lot.TempBand != temp {
			continue
		}
		row := lot
		row.Doses = left
		candidates = append(candidates, row)
	}
	st := loadRemainder()
	remain := need
	out := []api.LotAssignment{}
	for _, lot := range op_a(candidates) {
		if remain <= 0 {
			break
		}
		avail := p.left[lot.LotID]
		if avail <= 0 {
			continue
		}
		give := avail
		if give > remain {
			give = remain
		}
		remain -= give
		p.left[lot.LotID] = avail - give
		st[lot.LotID] = (st[lot.LotID] + give) % vial
		out = append(out, api.LotAssignment{LotID: lot.LotID, Doses: give, TempBand: lot.TempBand})
	}
	if err := saveRemainder(st); err != nil {
		return nil, err
	}
	return out, nil
}
