package cargograph

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"hash/crc32"
	"os"
	"path/filepath"
	"sort"
)

const capturesDir = "/app/crate-captures"

func CaptureDigest(scenarios []string) (string, error) {
	h := sha256.New()
	manifest, err := os.ReadFile(filepath.Join(capturesDir, "manifest.json"))
	if err != nil {
		return "", err
	}
	h.Write(manifest)
	for _, sid := range scenarios {
		data, err := os.ReadFile(filepath.Join(capturesDir, sid+".json"))
		if err != nil {
			return "", err
		}
		h.Write(data)
	}
	return hex.EncodeToString(h.Sum(nil)), nil
}

func CaptureChainTail(scenarios []string, digest string) (string, error) {
	chain, err := hex.DecodeString(digest)
	if err != nil {
		return "", err
	}
	for _, sid := range scenarios {
		data, err := os.ReadFile(filepath.Join(capturesDir, sid+".json"))
		if err != nil {
			return "", err
		}
		h := sha256.New()
		h.Write(chain)
		h.Write(data)
		chain = h.Sum(nil)
	}
	return hex.EncodeToString(chain), nil
}

func ManifestPayloadLen() (int, error) {
	data, err := os.ReadFile(filepath.Join(capturesDir, "manifest.json"))
	if err != nil {
		return 0, err
	}
	return len(data), nil
}

func BundledPayloadLen(scenarios []string) (int, error) {
	total := 0
	for _, sid := range scenarios {
		data, err := os.ReadFile(filepath.Join(capturesDir, sid+".json"))
		if err != nil {
			return 0, err
		}
		total += len(data)
	}
	return total, nil
}

func PayloadLenLE(n int) string {
	b := make([]byte, 4)
	v := uint32(n)
	b[0] = byte(v)
	b[1] = byte(v >> 8)
	b[2] = byte(v >> 16)
	b[3] = byte(v >> 24)
	return hex.EncodeToString(b)
}

func ManifestPayloadLenLE(n int) string { return PayloadLenLE(n) }
func BundledPayloadLenLE(n int) string  { return PayloadLenLE(n) }

func ScenarioPayloadDigest(scenarioID string) (string, error) {
	data, err := os.ReadFile(filepath.Join(capturesDir, scenarioID+".json"))
	if err != nil {
		return "", err
	}
	sum := sha256.Sum256(data)
	return hex.EncodeToString(sum[:]), nil
}

func ScenarioPayloadCRC32(scenarioID string) (string, error) {
	data, err := os.ReadFile(filepath.Join(capturesDir, scenarioID+".json"))
	if err != nil {
		return "", err
	}
	return fmt.Sprintf("%08x", crc32.ChecksumIEEE(data)), nil
}

func ScenarioPayloadLen(scenarioID string) (int, error) {
	data, err := os.ReadFile(filepath.Join(capturesDir, scenarioID+".json"))
	if err != nil {
		return 0, err
	}
	return len(data), nil
}

func ScenarioPayloadPlus(payloadLen, dup, frames, truncated int) int {
	return payloadLen + dup + frames + truncated
}

func CountPartialFeatureLiterals(crates []ResolvedCrate) int {
	count := 0
	for _, c := range crates {
		for _, f := range c.ActiveFeatures {
			if len(f) >= 5 && f[:5] == "feat:" {
				count++
			}
		}
	}
	return count
}

func ConflictRejectionCount(conflicts []FeatureConflict) int {
	total := 0
	for _, c := range conflicts {
		total += len(c.RejectedVersions)
	}
	return total
}

func SortFeatures(features []string) []string {
	if len(features) == 0 {
		return []string{}
	}
	out := append([]string(nil), features...)
	sort.Strings(out)
	return out
}

func UnionFeatures(a, b []string) []string {
	seen := make(map[string]struct{}, len(a)+len(b))
	for _, f := range a {
		seen[f] = struct{}{}
	}
	for _, f := range b {
		seen[f] = struct{}{}
	}
	out := make([]string, 0, len(seen))
	for f := range seen {
		out = append(out, f)
	}
	sort.Strings(out)
	return out
}

func CrateKey(crate, version string) string {
	return crate + ":" + version
}

func ParseSemver(v string) (int, int, int) {
	parts := [3]int{0, 0, 0}
	seg := 0
	num := 0
	hasNum := false
	for _, ch := range v {
		if ch >= '0' && ch <= '9' {
			num = num*10 + int(ch-'0')
			hasNum = true
			continue
		}
		if hasNum && seg < 3 {
			parts[seg] = num
			seg++
			num = 0
			hasNum = false
		}
		if ch == '.' {
			continue
		}
		if seg >= 2 {
			break
		}
	}
	if hasNum && seg < 3 {
		parts[seg] = num
	}
	return parts[0], parts[1], parts[2]
}

func SemverLess(a, b string) bool {
	aa, ab, ac := ParseSemver(a)
	ba, bb, bc := ParseSemver(b)
	if aa != ba {
		return aa < ba
	}
	if ab != bb {
		return ab < bb
	}
	return ac < bc
}

func SortVersions(versions []string) []string {
	out := append([]string(nil), versions...)
	sort.Slice(out, func(i, j int) bool { return SemverLess(out[i], out[j]) })
	return out
}

func ConflictSeverity(selected string, rejected []string) string {
	sm, _, _ := ParseSemver(selected)
	for _, r := range rejected {
		rm, _, _ := ParseSemver(r)
		if sm != rm {
			return "hard"
		}
	}
	return "soft"
}
