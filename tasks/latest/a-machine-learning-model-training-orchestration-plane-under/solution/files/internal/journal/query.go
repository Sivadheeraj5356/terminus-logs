package journal

import "sort"

// ByNode returns entries for a node ID sorted by seq.
func (l *Log) ByNode(nodeID string) []Entry {
	var out []Entry
	for _, e := range l.Entries {
		if e.NodeID == nodeID {
			out = append(out, e)
		}
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Seq < out[j].Seq })
	return out
}

// Actions returns distinct actions in seq order.
func (l *Log) Actions() []string {
	seen := map[string]struct{}{}
	var out []string
	entries := append([]Entry{}, l.Entries...)
	sort.Slice(entries, func(i, j int) bool { return entries[i].Seq < entries[j].Seq })
	for _, e := range entries {
		if _, ok := seen[e.Action]; ok {
			continue
		}
		seen[e.Action] = struct{}{}
		out = append(out, e.Action)
	}
	return out
}

// LastSeq returns the last sequence number or -1.
func (l *Log) LastSeq() int {
	if len(l.Entries) == 0 {
		return -1
	}
	max := l.Entries[0].Seq
	for _, e := range l.Entries[1:] {
		if e.Seq > max {
			max = e.Seq
		}
	}
	return max
}
