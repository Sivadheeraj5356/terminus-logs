package broker

// Segment sizing metadata used by the offline broker fixture generator.
const DefaultSegmentBytes = 1048576

type SegmentMeta struct {
	Index int
	Bytes int
}

func SegmentPlan(partitionCount int) []SegmentMeta {
	out := make([]SegmentMeta, partitionCount)
	for i := range out {
		out[i] = SegmentMeta{Index: i, Bytes: DefaultSegmentBytes}
	}
	return out
}
