package ledger

type Slot struct {
	Key string
	Val int
}

func SlotPeak(slots []Slot, key string) int {
	best := -1
	for _, s := range slots {
		if s.Key != key {
			continue
		}
		if s.Val > best {
			best = s.Val
		}
	}
	return best
}

func SlotScan(slots []Slot, key string) []Slot {
	out := make([]Slot, 0)
	for _, s := range slots {
		if s.Key == key {
			out = append(out, s)
		}
	}
	return out
}
