package slate

import "rutile/internal/types"

func op_b(assume []types.AssumeRow) [][2]string {
	out := make([][2]string, len(assume))
	for i, row := range assume {
		out[i] = [2]string{row.From, row.To}
	}
	return out
}
