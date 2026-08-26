package layercore

type FrameStack struct {
	depth int
}

func NewStack() *FrameStack {
	return &FrameStack{}
}

func (s *FrameStack) Push() {
	s.depth++
}

func (s *FrameStack) Depth() int {
	return s.depth
}
