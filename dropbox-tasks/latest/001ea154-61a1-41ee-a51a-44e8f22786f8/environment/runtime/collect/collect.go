package collect

import "streamkit/internal/model"

func RecordWeight(rec model.Record) int {
	return 1024 + len(rec.Value)*256
}

func mergeUnits(available, maxRecords, minBytes int, recs []model.Record) []model.Record {
	if available <= 0 || len(recs) == 0 {
		return nil
	}
	if maxRecords <= 0 || maxRecords > len(recs) {
		maxRecords = len(recs)
	}
	if minBytes <= 0 {
		return recs[:maxRecords]
	}

	budget := minBytes
	out := []model.Record{}
	for _, rec := range recs {
		if len(out) >= maxRecords {
			break
		}
		cost := RecordWeight(rec)
		if cost > budget {
			if len(out) == 0 {
				out = append(out, rec)
			}
			break
		}
		out = append(out, rec)
		budget -= cost
	}
	return out
}

func Collect(recs []model.Record, available, maxRecords, minBytes int, useByteCredit bool) []model.Record {
	if !useByteCredit {
		minBytes = 0
	}
	return mergeUnits(available, maxRecords, minBytes, recs)
}
