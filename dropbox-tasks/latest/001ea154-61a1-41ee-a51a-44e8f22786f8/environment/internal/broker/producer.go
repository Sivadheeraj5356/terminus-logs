package broker

import "streamkit/internal/model"

type Producer struct {
	topic *Topic
}

func NewProducer(topic *Topic) *Producer {
	return &Producer{topic: topic}
}

func (p *Producer) Publish(partition int, rec model.Record) int {
	if partition < 0 || partition >= len(p.topic.Partitions) {
		return -1
	}
	part := &p.topic.Partitions[partition]
	rec.Offset = part.HWM
	part.Records = append(part.Records, rec)
	part.HWM++
	return rec.Offset
}
