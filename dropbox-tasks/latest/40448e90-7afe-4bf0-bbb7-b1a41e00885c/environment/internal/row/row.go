package row

import (
	"bytes"
	"encoding/json"
	"sort"

	"kvlab/internal/hash"
)

type RunRow struct {
	Profile               string `json:"profile"`
	RunIndex              int    `json:"run_index"`
	RoleVersion           int    `json:"role_version"`
	ContentDigest         string `json:"content_digest"`
	DelegationExpiry      int64  `json:"delegation_expiry"`
	StageTranscriptHex string `json:"stage_transcript_hex"`
}

type Export struct {
	Profiles     []string  `json:"profiles"`
	Runs         []RunRow  `json:"runs"`
	ReportDigest string    `json:"report_digest"`
}

func CanonicalRunsJSON(runs []RunRow) []byte {
	cp := append([]RunRow(nil), runs...)
	sort.Slice(cp, func(i, j int) bool {
		if cp[i].Profile != cp[j].Profile {
			return cp[i].Profile < cp[j].Profile
		}
		return cp[i].RunIndex < cp[j].RunIndex
	})
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetEscapeHTML(false)
	_ = enc.Encode(cp)
	out := bytes.TrimSpace(buf.Bytes())
	return out
}

func ReportDigest(runs []RunRow) string {
	return hash.Hex(CanonicalRunsJSON(runs))
}

func MergeProfiles(existing []string, add string) []string {
	seen := map[string]struct{}{}
	out := append([]string(nil), existing...)
	for _, p := range out {
		seen[p] = struct{}{}
	}
	if _, ok := seen[add]; !ok {
		out = append(out, add)
	}
	sort.Strings(out)
	return out
}
