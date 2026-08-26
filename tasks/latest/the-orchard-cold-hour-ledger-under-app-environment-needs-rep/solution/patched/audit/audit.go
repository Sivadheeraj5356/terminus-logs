package audit

import (
	"fmt"
	"strings"
)

type Row struct {
	OrchardID         string
	SensorID          string
	BucketEpoch       int64
	RawSamples        int
	AcceptedSamples   int
	TombstonedSamples int
	SplitSegments     int
	InputHash         string
}

func FormatTSV(rows []Row) string {
	var b strings.Builder
	b.WriteString("orchard_id\tsensor_id\tbucket_epoch\traw_samples\taccepted_samples\ttombstoned_samples\tsplit_segments\tinput_hash\n")
	for _, r := range rows {
		fmt.Fprintf(&b, "%s\t%s\t%d\t%d\t%d\t%d\t%d\t%s\n",
			r.OrchardID, r.SensorID, r.BucketEpoch,
			r.RawSamples, r.AcceptedSamples, r.TombstonedSamples, r.SplitSegments, r.InputHash)
	}
	return b.String()
}
