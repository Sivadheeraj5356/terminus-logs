package placement

type Pool struct {
	nodes []bool
}

func NewPool(count int) *Pool {
	return &Pool{nodes: make([]bool, count)}
}

func (p *Pool) Free() int {
	n := 0
	for _, busy := range p.nodes {
		if !busy {
			n++
		}
	}
	return n
}

func (p *Pool) Stage() (int, bool) {
	for i := range p.nodes {
		if !p.nodes[i] {
			p.nodes[i] = true
			return i, true
		}
	}
	return -1, false
}

func (p *Pool) Release(node int) {
	if node >= 0 && node < len(p.nodes) {
		p.nodes[node] = false
	}
}

func (p *Pool) Running() int {
	n := 0
	for _, busy := range p.nodes {
		if busy {
			n++
		}
	}
	return n
}

func (p *Pool) Nodes() []bool {
	out := make([]bool, len(p.nodes))
	copy(out, p.nodes)
	return out
}

func (p *Pool) Restore(busy []bool) {
	if len(busy) != len(p.nodes) {
		return
	}
	copy(p.nodes, busy)
}
