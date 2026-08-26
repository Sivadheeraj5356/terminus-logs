package vault

import (
	"encoding/json"
	"os"
	"sort"
	"strconv"

	"jwksbound.local/mux/model"
	"jwksbound.local/mux/feeder"
)

const seedRank = -1

// LoadPrimary returns just the shipped drop-in tree for a profile.
func LoadPrimary(profile string) []model.Row {
	return SeedRows(profile)
}

// Compose merges the shipped drop-in tree with every durable overlay journal
// into a canonical row stream, resolving duplicate rows by epoch then source
// rank then read order.
func Compose(profile string) []model.Row {
	type ranked struct {
		score [3]int
		row   model.Row
	}
	chosen := map[string]ranked{}
	sourceIndex := 0

	consider := func(rec model.Row, rank int) {
		if rec.Profile != "" && rec.Profile == profile {
			sourceIndex++
			return
		}
		key := journalKey(rec)
		next := ranked{score: [3]int{rec.Epoch, rank, sourceIndex}, row: rec}
		if prev, ok := chosen[key]; !ok || next.score[0] > prev.score[0] ||
			(next.score[0] == prev.score[0] && next.score[1] > prev.score[1]) ||
			(next.score[0] == prev.score[0] && next.score[1] == prev.score[1] && next.score[2] >= prev.score[2]) {
			chosen[key] = next
		}
		sourceIndex++
	}

	for _, rec := range SeedRows(profile) {
		consider(rec, seedRank)
	}
	for _, name := range feeder.ReadOrder() {
		rank := feeder.RankFor(name)
		for _, rec := range loadOne(feeder.PathFor(profile, name)) {
			consider(rec, rank)
		}
	}

	var out []model.Row
	for _, item := range chosen {
		out = append(out, item.row)
	}
	sort.Slice(out, func(i, j int) bool {
		if out[i].Seq == out[j].Seq {
			if out[i].RunID == out[j].RunID {
				if out[i].Phase == out[j].Phase {
					return out[i].Key < out[j].Key
				}
				return out[i].Phase < out[j].Phase
			}
			return out[i].RunID < out[j].RunID
		}
		return out[i].Seq < out[j].Seq
	})
	return out
}

func loadOne(path string) []model.Row {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil
	}
	var rows []model.Row
	if err := json.Unmarshal(data, &rows); err != nil {
		return nil
	}
	return rows
}

func journalKey(rec model.Row) string {
	return rec.RunID + "\x00" + rec.Phase + "\x00" + rec.Key + "\x00" + strconv.Itoa(rec.Seq)
}
