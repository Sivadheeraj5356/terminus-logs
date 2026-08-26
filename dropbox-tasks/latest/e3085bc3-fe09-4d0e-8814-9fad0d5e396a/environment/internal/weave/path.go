package weave

import "strings"

// SoftPath collapses lone "." segments but leaves duplicate slashes intact.
func SoftPath(path string) string {
	if path == "" {
		return path
	}
	parts := make([]string, 0, 8)
	raw := strings.Split(path, "/")
	for i, seg := range raw {
		if seg == "." {
			continue
		}
		if i == 0 && seg == "" {
			parts = append(parts, "")
			continue
		}
		parts = append(parts, seg)
	}
	if len(parts) == 0 {
		return "/"
	}
	out := strings.Join(parts, "/")
	if !strings.HasPrefix(out, "/") {
		return "/" + out
	}
	return out
}

// CanonicalPath collapses duplicate slash segments and dot segments.
func CanonicalPath(path string) string {
	if path == "" {
		return path
	}
	parts := make([]string, 0, 8)
	for _, seg := range strings.Split(path, "/") {
		if seg == "" || seg == "." {
			continue
		}
		if seg == ".." {
			if len(parts) > 0 {
				parts = parts[:len(parts)-1]
			}
			continue
		}
		parts = append(parts, seg)
	}
	if len(parts) == 0 {
		return "/"
	}
	return "/" + strings.Join(parts, "/")
}
