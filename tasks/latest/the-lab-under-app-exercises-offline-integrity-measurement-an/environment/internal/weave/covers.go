package weave

// Holds reports whether root encloses path.
func Holds(root, path string) bool {
	if root == path {
		return true
	}
	if root == "/" {
		return true
	}
	if len(path) <= len(root) {
		return false
	}
	if path[:len(root)] != root {
		return false
	}
	return true
}

// WantsLog reports whether verb list includes logging.
func WantsLog(verbs []int) bool {
	for _, v := range verbs {
		if v == 1 {
			return true
		}
	}
	return false
}

// WantsCheck reports whether verb list includes appraisal.
func WantsCheck(verbs []int) bool {
	for _, v := range verbs {
		if v == 2 || v == 4 {
			return true
		}
	}
	return false
}
