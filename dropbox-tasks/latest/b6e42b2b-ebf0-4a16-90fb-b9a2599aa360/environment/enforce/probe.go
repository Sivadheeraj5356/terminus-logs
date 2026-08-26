package enforce

import (
	"arctl.local/arctl/model"
)

func LocalReady(treeSD string, state model.PersistedState) bool {
	if treeSD == "" {
		return false
	}
	return treeSD == state.TreeSD
}

func ProbeReady(treeSD string, state model.PersistedState) string {
	if LocalReady(treeSD, state) {
		return "ready"
	}
	return "pending"
}
