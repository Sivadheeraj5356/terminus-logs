package export

import (
	"encoding/json"
	"io"
	"sort"

	"kvlab/internal/row"
)

func Rollup(rows []row.RunRow, sink io.Writer) error {
	profiles := []string{}
	seen := map[string]struct{}{}
	filtered := []row.RunRow{}
	active := ""
	if len(rows) > 0 {
		active = rows[len(rows)-1].Profile
	}
	for _, r := range rows {
		if r.Profile != active {
			continue
		}
		if len(filtered) > 0 && r.RunIndex <= filtered[len(filtered)-1].RunIndex {
			continue
		}
		filtered = append(filtered, r)
	}
	for _, r := range filtered {
		if _, ok := seen[r.Profile]; !ok {
			seen[r.Profile] = struct{}{}
			profiles = append(profiles, r.Profile)
		}
	}
	sort.Strings(profiles)
	doc := row.Export{
		Profiles:     profiles,
		Runs:         filtered,
		ReportDigest: row.ReportDigest(filtered),
	}
	enc := json.NewEncoder(sink)
	enc.SetEscapeHTML(false)
	enc.SetIndent("", "")
	return enc.Encode(doc)
}
