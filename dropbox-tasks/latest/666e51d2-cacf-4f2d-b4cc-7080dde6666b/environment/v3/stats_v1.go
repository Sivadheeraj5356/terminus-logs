package v3

import "s8lab/types"

func CountRows(rows []types.Row) int {
	return len(rows)
}

func SumEras(rows []types.Row) int {
	total := 0
	for _, row := range rows {
		total += row.Era
	}
	return total
}

func WriteMarkers(rows []types.Row, gen uint64, outDir string) error {
	return pack_u8(rows, gen, outDir)
}
