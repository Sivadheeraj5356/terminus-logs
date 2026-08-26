package emit

import (
	"bytes"
	"encoding/json"
	"sort"

	"orchard/canopyledger/accum"
	"orchard/canopyledger/audit"
	"orchard/canopyledger/util"
)

func WriteLedger(path string, rows []accum.Row) error {
	sort.Slice(rows, func(i, j int) bool {
		ri, rj := rows[i], rows[j]
		if ri.BucketEpoch != rj.BucketEpoch {
			return ri.BucketEpoch < rj.BucketEpoch
		}
		return ri.SensorID < rj.SensorID
	})
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	for _, row := range rows {
		if err := enc.Encode(row); err != nil {
			return err
		}
	}
	return util.AtomicWrite(path, buf.Bytes())
}

func WriteReplayLedger(path string, rows []accum.Row) error {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].BucketEpoch != rows[j].BucketEpoch {
			return rows[i].BucketEpoch < rows[j].BucketEpoch
		}
		return rows[i].SensorID < rows[j].SensorID
	})
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	for _, row := range rows {
		obj := map[string]any{
			"orchard_id":   row.OrchardID,
			"sensor_id":    row.SensorID,
			"bucket_epoch": row.BucketEpoch,
			"credit_hours": row.CreditHours,
			"sample_count": row.SampleCount,
		}
		if err := enc.Encode(obj); err != nil {
			return err
		}
	}
	return util.AtomicWrite(path, buf.Bytes())
}

func WriteAudit(path string, rows []audit.Row) error {
	return util.AtomicWrite(path, []byte(audit.FormatTSV(rows)))
}

func EncodeReplayLedger(rows []accum.Row) ([]byte, error) {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].BucketEpoch != rows[j].BucketEpoch {
			return rows[i].BucketEpoch < rows[j].BucketEpoch
		}
		return rows[i].SensorID < rows[j].SensorID
	})
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	for _, row := range rows {
		obj := map[string]any{
			"orchard_id":   row.OrchardID,
			"sensor_id":    row.SensorID,
			"bucket_epoch": row.BucketEpoch,
			"credit_hours": row.CreditHours,
			"sample_count": row.SampleCount,
		}
		if err := enc.Encode(obj); err != nil {
			return nil, err
		}
	}
	return buf.Bytes(), nil
}
