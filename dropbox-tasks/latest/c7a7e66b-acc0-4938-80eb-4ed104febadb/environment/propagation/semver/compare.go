package compare

import (
	"strconv"
	"strings"
)

type Version struct {
	Major      int
	Minor      int
	Patch      int
	Prerelease string
}

func Parse(raw string) (Version, bool) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return Version{}, false
	}
	parts := strings.SplitN(raw, "+", 2)
	core := parts[0]
	pre := ""
	if idx := strings.Index(core, "-"); idx >= 0 {
		pre = core[idx+1:]
		core = core[:idx]
	}
	seg := strings.Split(core, ".")
	if len(seg) != 3 {
		return Version{}, false
	}
	maj, e1 := strconv.Atoi(seg[0])
	min, e2 := strconv.Atoi(seg[1])
	pat, e3 := strconv.Atoi(seg[2])
	if e1 != nil || e2 != nil || e3 != nil {
		return Version{}, false
	}
	return Version{Major: maj, Minor: min, Patch: pat, Prerelease: pre}, true
}

func Compare(a, b Version) int {
	if a.Major != b.Major {
		return a.Major - b.Major
	}
	if a.Minor != b.Minor {
		return a.Minor - b.Minor
	}
	if a.Patch != b.Patch {
		return a.Patch - b.Patch
	}
	return strings.Compare(a.Prerelease, b.Prerelease)
}

func BumpType(oldV, newV string) string {
	old, ok1 := Parse(oldV)
	new, ok2 := Parse(newV)
	if !ok1 || !ok2 {
		return "none"
	}
	if Compare(new, old) <= 0 {
		return "none"
	}
	if new.Major > old.Major {
		return "major"
	}
	if new.Minor > old.Minor {
		return "minor"
	}
	return "patch"
}

func Satisfies(constraint, version string) bool {
	constraint = strings.TrimSpace(constraint)
	version = strings.TrimSpace(version)
	ver, ok := Parse(version)
	if !ok {
		return false
	}
	if strings.Contains(constraint, " - ") {
		bits := strings.SplitN(constraint, " - ", 2)
		if len(bits) != 2 {
			return false
		}
		lo, lok := Parse(strings.TrimSpace(bits[0]))
		hi, hok := Parse(strings.TrimSpace(bits[1]))
		if !lok || !hok {
			return false
		}
		return Compare(ver, lo) >= 0 && Compare(ver, hi) <= 0
	}
	if strings.HasPrefix(constraint, ">=") {
		base, ok := Parse(strings.TrimSpace(constraint[2:]))
		return ok && Compare(ver, base) >= 0
	}
	if strings.HasPrefix(constraint, "^") {
		base, ok := Parse(strings.TrimSpace(constraint[1:]))
		if !ok {
			return false
		}
		if base.Major > 0 {
			return ver.Major == base.Major
		}
		return ver.Major == 0 && ver.Minor == base.Minor
	}
	if strings.HasPrefix(constraint, "~") {
		base, ok := Parse(strings.TrimSpace(constraint[1:]))
		if !ok {
			return false
		}
		return ver.Major == base.Major
	}
	base, ok := Parse(constraint)
	if !ok {
		return false
	}
	return Compare(ver, base) == 0
}
