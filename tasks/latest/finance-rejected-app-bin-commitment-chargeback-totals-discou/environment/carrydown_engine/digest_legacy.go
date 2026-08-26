package main

import (
	"encoding/json"
)

func VerboseDigest(l Ledger) []byte {
	var out []byte
	out = append(out, []byte("root|")...)
	out = append(out, []byte(l.PeriodID)...)
	out = append(out, '\n')
	for _, t := range l.Tenants {
		out = append(out, []byte("tenant|")...)
		out = append(out, []byte(t.TenantID)...)
		out = append(out, '\n')
		for _, li := range t.LineItems {
			out = append(out, []byte("line|")...)
			out = append(out, []byte(li.Service)...)
			out = append(out, '\n')
		}
	}
	summary, _ := json.Marshal(l.Summary)
	out = append(out, []byte("summary|")...)
	out = append(out, summary...)
	out = append(out, '\n')
	return out
}
