package closure

// Expand propagates reachability through intermediate principals for a seeded pair set.
func Expand(pairs [][2]string) [][2]string {
	edges := map[[2]string]struct{}{}
	for _, pair := range pairs {
		edges[pair] = struct{}{}
	}
	changed := true
	for changed {
		changed = false
		for a := range edges {
			for b := range edges {
				if a[1] != b[0] {
					continue
				}
				pair := [2]string{a[0], b[1]}
				if _, ok := edges[pair]; !ok {
					edges[pair] = struct{}{}
					changed = true
				}
			}
		}
	}
	out := make([][2]string, 0, len(edges))
	for pair := range edges {
		out = append(out, pair)
	}
	return out
}
