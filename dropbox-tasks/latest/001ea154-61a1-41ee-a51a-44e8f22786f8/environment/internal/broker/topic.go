package broker

import "streamkit/internal/model"

type Partition struct {
	Records []model.Record
	HWM     int
}

type Topic struct {
	Name       string
	Partitions []Partition
}

func NewTopic(name string, partitionCount, recordsPerPartition int) *Topic {
	t := &Topic{Name: name, Partitions: make([]Partition, partitionCount)}
	for p := 0; p < partitionCount; p++ {
		rows := make([]model.Record, recordsPerPartition)
		for o := 0; o < recordsPerPartition; o++ {
			rows[o] = model.Record{
				Offset: o,
				Key:    name,
				Value:  "evt",
			}
		}
		t.Partitions[p] = Partition{Records: rows, HWM: recordsPerPartition}
	}
	return t
}

func (t *Topic) ReadFrom(partition, offset, limit int) []model.Record {
	if partition < 0 || partition >= len(t.Partitions) {
		return nil
	}
	part := t.Partitions[partition]
	if offset >= part.HWM {
		return nil
	}
	end := offset + limit
	if end > part.HWM {
		end = part.HWM
	}
	return part.Records[offset:end]
}

func (t *Topic) Lag(partition, committed int) int {
	if partition < 0 || partition >= len(t.Partitions) {
		return 0
	}
	return t.Partitions[partition].HWM - committed
}

func (t *Topic) TotalRecords() int {
	total := 0
	for _, p := range t.Partitions {
		total += p.HWM
	}
	return total
}
