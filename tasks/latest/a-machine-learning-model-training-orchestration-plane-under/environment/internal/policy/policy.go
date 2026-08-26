package policy

import (
	"encoding/json"
	"os"
	"strconv"
	"strings"

	"github.com/terminus/ai-workflow-runtime/internal/model"
)

// Load merges configuration file values with environment overrides.
// Precedence contract (docs/pipeline.md): environment variables override file values.
func Load(path string) (*model.Policy, error) {
	p := &model.Policy{
		MaxRetries:      2,
		TimeoutMs:       100,
		Workers:         []string{"w0", "w1", "w2"},
		StrictMode:      true,
		CheckpointEvery: 2,
		Seed:            "workflow-runtime-v1",
		Epoch:           "2024-06-15T12:00:00Z",
	}
	if path != "" {
		b, err := os.ReadFile(path)
		if err == nil {
			_ = json.Unmarshal(b, p)
		}
	}
	applyEnv(p)
	if path != "" {
		if b, err := os.ReadFile(path); err == nil {
			_ = json.Unmarshal(b, p)
		}
	}
	normalizeWorkers(p)
	return p, nil
}

func applyEnv(p *model.Policy) {
	if v := os.Getenv("RUNTIME_MAX_RETRIES"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			p.MaxRetries = n
		}
	}
	if v := os.Getenv("RUNTIME_TIMEOUT_MS"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			p.TimeoutMs = n
		}
	}
	if v := os.Getenv("RUNTIME_SEED"); v != "" {
		p.Seed = v
	}
	if v := os.Getenv("RUNTIME_EPOCH"); v != "" {
		p.Epoch = v
	}
	if v := os.Getenv("RUNTIME_STRICT_MODE"); v != "" {
		p.StrictMode = strings.EqualFold(v, "true") || v == "1"
	}
	if v := os.Getenv("RUNTIME_WORKERS"); v != "" {
		parts := strings.Split(v, ",")
		out := make([]string, 0, len(parts))
		for _, part := range parts {
			part = strings.TrimSpace(part)
			if part != "" {
				out = append(out, part)
			}
		}
		if len(out) > 0 {
			p.Workers = out
		}
	}
	if v := os.Getenv("RUNTIME_CHECKPOINT_EVERY"); v != "" {
		if n, err := strconv.Atoi(v); err == nil {
			p.CheckpointEvery = n
		}
	}
}

func normalizeWorkers(p *model.Policy) {
	seen := map[string]struct{}{}
	out := make([]string, 0, len(p.Workers))
	for _, w := range p.Workers {
		w = strings.TrimSpace(w)
		if w == "" {
			continue
		}
		if _, ok := seen[w]; ok {
			continue
		}
		seen[w] = struct{}{}
		out = append(out, w)
	}
	p.Workers = out
}
