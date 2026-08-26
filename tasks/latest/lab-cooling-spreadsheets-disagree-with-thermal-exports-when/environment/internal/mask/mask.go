package mask

type Grid struct {
	Width  int
	Height int
	Data   []bool
}

func FromGray16(data []uint16, width, height int, threshold uint16) *Grid {
	g := &Grid{Width: width, Height: height, Data: make([]bool, width*height)}
	for i, v := range data {
		g.Data[i] = v >= threshold
	}
	return g
}

func Combine(a, b *Grid) *Grid {
	if a.Width != b.Width || a.Height != b.Height {
		panic("mask size mismatch")
	}
	out := &Grid{Width: a.Width, Height: a.Height, Data: make([]bool, len(a.Data))}
	for i := range a.Data {
		out.Data[i] = a.Data[i] && b.Data[i]
	}
	return out
}
