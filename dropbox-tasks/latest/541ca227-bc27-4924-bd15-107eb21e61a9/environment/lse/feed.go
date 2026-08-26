package lse

import (
	"bufio"
	"encoding/json"
	"os"
)

type LeaseEvent struct {
	Kind   string `json:"kind"`
	Prefix string `json:"prefix"`
	Seq    int    `json:"seq"`
}

type FeedState struct {
	Epoch      uint64          `json:"epoch"`
	Fence      uint64          `json:"fence"`
	LastSeq    int             `json:"last_seq"`
	ActivePref map[string]bool `json:"active_pref"`
}

func NewFeedState() *FeedState {
	return &FeedState{ActivePref: map[string]bool{}}
}

func LoadEvents(path string) ([]LeaseEvent, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	var out []LeaseEvent
	sc := bufio.NewScanner(f)
	for sc.Scan() {
		line := sc.Bytes()
		if len(line) == 0 {
			continue
		}
		var ev LeaseEvent
		if err := json.Unmarshal(line, &ev); err != nil {
			return nil, err
		}
		out = append(out, ev)
	}
	return out, sc.Err()
}

func ReplayFeed(st *FeedState, events []LeaseEvent, upto int) {
	st.Epoch = 0
	st.Fence = 0
	st.LastSeq = 0
	st.ActivePref = map[string]bool{}
	for _, ev := range events {
		if upto >= 0 && ev.Seq > upto {
			continue
		}
		BumpFeed(st, ev)
	}
}
