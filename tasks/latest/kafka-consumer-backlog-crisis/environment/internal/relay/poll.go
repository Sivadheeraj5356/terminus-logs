package relay

import "streamkit/internal/broker"

func PollTopic(topic *broker.Topic, lanes []int, offsets map[int]int, tick int, pull func([]int, int) []int) []int {
	active := pull(lanes, tick)
	if len(active) == 0 {
		return nil
	}
	_ = topic
	_ = offsets
	return active
}
