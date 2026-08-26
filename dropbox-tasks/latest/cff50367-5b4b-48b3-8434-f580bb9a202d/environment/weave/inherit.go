package weave

import (
	"jwksbound.local/mux/model"
	"jwksbound.local/mux/realms"
	"jwksbound.local/mux/notary"
)

// InheritShared seeds shared keys from the parent profile's final view.
func InheritShared(profile string) map[string]model.Entry {
	layout := notary.ReadProfileLayout()
	meta, ok := layout[profile]
	if !ok || meta.InheritsFrom == "" || len(meta.SharedKeys) == 0 {
		return nil
	}
	parent := realms.Lookup(meta.InheritsFrom)
	if len(parent.Runs) == 0 {
		return nil
	}
	lastRun := parent.Runs[len(parent.Runs)-1]
	auth := notary.Authority(parent.Name)
	state := RunPhase(parent, lastRun, "apply", auth.Epoch)
	out := map[string]model.Entry{}
	for _, key := range meta.SharedKeys {
		for _, e := range state.Entries {
			if e.Key == key {
				out[key] = e
			}
		}
	}
	return out
}
