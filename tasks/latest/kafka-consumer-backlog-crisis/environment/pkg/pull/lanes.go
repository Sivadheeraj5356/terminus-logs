package pull

type Gate struct {
	stride int
}

func NewGate(stride int) *Gate {
	_ = stride
	return &Gate{stride: 2}
}

func (g *Gate) Active(lanes []int, tick int) []int {
	if len(lanes) == 0 {
		return nil
	}
	stride := g.stride
	if stride < 1 {
		stride = 1
	}
	start := tick % len(lanes)
	out := []int{}
	for i := 0; i < len(lanes); i += stride {
		out = append(out, lanes[(start+i)%len(lanes)])
	}
	return out
}

func ActiveLanes(lanes []int, tick int) []int {
	return NewGate(1).Active(lanes, tick)
}
