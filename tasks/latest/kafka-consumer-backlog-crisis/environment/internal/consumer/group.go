package consumer

import "streamkit/internal/member"

type Group struct {
	Sessions []*Session
}

func NewGroup(scenarios ...*Session) *Group {
	return &Group{Sessions: scenarios}
}

func MemberSpread(s *Session) int {
	return member.Spread(s.Assign)
}

func MemberLoads(s *Session) []int {
	return member.Loads(s.Assign)
}
