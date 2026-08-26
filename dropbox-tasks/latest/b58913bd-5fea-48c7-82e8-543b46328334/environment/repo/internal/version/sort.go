package version

import "sort"

// Sort orders formula version strings oldest-first, using the same comparison
// the resolver applies when it picks the newest release. The catalog tooling
// calls this before rendering a formula's release history.
func Sort(versions []string) {
	sort.SliceStable(versions, func(i, j int) bool {
		return Compare(versions[i], versions[j]) < 0
	})
}

// Newest returns the newest of the given versions, or the empty string when
// the slice is empty.
func Newest(versions []string) string {
	if len(versions) == 0 {
		return ""
	}
	newest := versions[0]
	for _, v := range versions[1:] {
		if Compare(v, newest) > 0 {
			newest = v
		}
	}
	return newest
}
