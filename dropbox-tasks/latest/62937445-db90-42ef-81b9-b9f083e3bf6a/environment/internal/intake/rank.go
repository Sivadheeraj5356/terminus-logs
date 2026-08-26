package intake

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"
	"strings"

	"ra.local/field/internal/domain"
)

func Rank(rows []domain.Observation) ([]domain.Observation, []domain.RunRecord) {
	byRun := make(map[string][]int)
	for index := range rows {
		byRun[rows[index].Run] = append(byRun[rows[index].Run], index)
	}
	runIDs := make([]string, 0, len(byRun))
	for run := range byRun {
		runIDs = append(runIDs, run)
	}
	sort.Strings(runIDs)
	runs := make([]domain.RunRecord, 0, len(runIDs))
	for _, run := range runIDs {
		indices := byRun[run]
		sort.Slice(indices, func(i, j int) bool {
			left, right := rows[indices[i]], rows[indices[j]]
			if left.Time != right.Time {
				return left.Time < right.Time
			}
			return left.ID < right.ID
		})
		if len(indices) == 1 {
			rows[indices[0]].Coordinate = 0.5
		} else {
			for start := 0; start < len(indices); {
				end := start + 1
				for end < len(indices) && rows[indices[end]].Time == rows[indices[start]].Time {
					end++
				}
				midrank := float64(start+end-1) / 2.0
				coordinate := midrank / float64(len(indices)-1)
				for cursor := start; cursor < end; cursor++ {
					rows[indices[cursor]].Coordinate = coordinate
				}
				start = end
			}
		}
		ids := make([]string, 0, len(indices))
		var material strings.Builder
		for _, index := range indices {
			ids = append(ids, rows[index].ID)
			fmt.Fprintf(&material, "%s=%.17g\n", rows[index].ID, rows[index].Coordinate)
		}
		sort.Strings(ids)
		sum := sha256.Sum256([]byte(material.String()))
		runs = append(runs, domain.RunRecord{
			Run: run, ObservationIDs: ids, CoordinateHash: hex.EncodeToString(sum[:]),
		})
	}
	sort.Slice(rows, func(i, j int) bool { return rows[i].ID < rows[j].ID })
	return rows, runs
}
