package model

type FetchUnit struct {
	Partition int
	Records   []Record
}

type OffsetMark struct {
	Partition int
	Offset    int
}
