package policy

import (
	"os"
	"strings"
)

func parseFlatKV(path string) map[string]string {
	out := map[string]string{}
	b, err := os.ReadFile(path)
	if err != nil {
		return out
	}
	for _, line := range strings.Split(string(b), "\n") {
		trim := strings.TrimSpace(line)
		if trim == "" || strings.HasPrefix(trim, "#") || strings.HasPrefix(trim, "[") {
			continue
		}
		parts := strings.SplitN(trim, "=", 2)
		if len(parts) != 2 {
			continue
		}
		out[strings.TrimSpace(parts[0])] = strings.Trim(strings.TrimSpace(parts[1]), `"`)
	}
	return out
}

func applyBind(cfg *Config, kv map[string]string) {
	if v, ok := kv["mask_from_checkpoint_gen"]; ok {
		if b, ok := asBool(v); ok {
			cfg.ResumeMaskFromCheckpoint = b
		}
	}
	if v, ok := kv["per_peer_stride"]; ok {
		if b, ok := asBool(v); ok {
			cfg.LanePerPeerStride = b
		}
	}
}
