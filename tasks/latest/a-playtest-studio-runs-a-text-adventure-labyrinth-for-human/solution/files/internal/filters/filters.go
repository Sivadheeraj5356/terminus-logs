// Package filters holds the small predicates the assemble lane applies to a
// staged candidate before it becomes a live next-action suggestion: does the
// session hold every required item, and has the target already been consumed
// or taken.
package filters

// InventoryOK reports whether inventory satisfies every entry in required.
func InventoryOK(required, inventory []string) bool {
	if len(required) == 0 {
		return true
	}
	held := toSet(inventory)
	for _, item := range required {
		if !held[item] {
			return false
		}
	}
	return true
}

// NotIn reports whether needle is absent from haystack.
func NotIn(needle string, haystack []string) bool {
	for _, v := range haystack {
		if v == needle {
			return false
		}
	}
	return true
}

func toSet(list []string) map[string]bool {
	set := make(map[string]bool, len(list))
	for _, v := range list {
		set[v] = true
	}
	return set
}
