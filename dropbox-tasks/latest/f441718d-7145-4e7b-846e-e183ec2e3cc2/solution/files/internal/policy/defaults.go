package policy

import "github.com/terminus/ai-workflow-runtime/internal/model"

// Default returns the built-in policy used when no file/env is present.
func Default() *model.Policy {
	return &model.Policy{
		MaxRetries:      2,
		TimeoutMs:       100,
		Workers:         []string{"w0", "w1", "w2"},
		StrictMode:      true,
		CheckpointEvery: 2,
		Seed:            "workflow-runtime-v1",
		Epoch:           "2024-06-15T12:00:00Z",
	}
}

// Clone returns a shallow copy of policy with cloned worker slice.
func Clone(p *model.Policy) *model.Policy {
	if p == nil {
		return Default()
	}
	out := *p
	out.Workers = append([]string{}, p.Workers...)
	return &out
}
