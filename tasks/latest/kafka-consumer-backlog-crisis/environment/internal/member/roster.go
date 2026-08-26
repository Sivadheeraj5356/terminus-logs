package member

func RebalanceTail(assign [][]int) [][]int {
	if len(assign) == 0 {
		return assign
	}
	out := make([][]int, len(assign))
	for i := range assign {
		out[i] = append([]int(nil), assign[i]...)
	}
	tail := len(out) - 1
	for seat := 0; seat < tail; seat++ {
		if len(out[seat]) <= len(out[tail]) {
			continue
		}
		move := out[seat][len(out[seat])-1]
		out[seat] = out[seat][:len(out[seat])-1]
		out[tail] = append(out[tail], move)
	}
	return out
}
