package k5

import (
	"encoding/json"
	"fmt"
	"strings"

	"s8lab/types"
)

func FormatSegments(rows []types.StreamRow) string {
	var b strings.Builder
	for _, row := range rows {
		raw, _ := json.Marshal(row)
		fmt.Fprintf(&b, "%s\n", string(raw))
	}
	return b.String()
}

func InspectSegments(rows []types.StreamRow) string {
	return FormatSegments(rows)
}
