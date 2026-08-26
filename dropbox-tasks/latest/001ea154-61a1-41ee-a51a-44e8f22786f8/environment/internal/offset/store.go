package offset

type Store struct {
	marks map[int]int
}

func NewStore() *Store {
	return &Store{marks: map[int]int{}}
}

func (s *Store) Get(partition int) int {
	if v, ok := s.marks[partition]; ok {
		return v
	}
	return 0
}

func (s *Store) Set(partition, offset int) {
	s.marks[partition] = offset
}

func (s *Store) Snapshot() map[int]int {
	out := make(map[int]int, len(s.marks))
	for k, v := range s.marks {
		out[k] = v
	}
	return out
}
