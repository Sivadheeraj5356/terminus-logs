package member

import "streamkit/internal/model"

type Registry struct {
	Members []model.Member
}

func NewRegistry(count int) *Registry {
	members := make([]model.Member, count)
	for i := 0; i < count; i++ {
		members[i] = model.Member{ID: memberID(i)}
	}
	return &Registry{Members: members}
}

func memberID(i int) string {
	const alphabet = "abcdefghijklmnopqrstuvwxyz"
	if i < 26 {
		return string(alphabet[i])
	}
	return string(alphabet[i%26]) + string(rune('0'+i/26))
}
