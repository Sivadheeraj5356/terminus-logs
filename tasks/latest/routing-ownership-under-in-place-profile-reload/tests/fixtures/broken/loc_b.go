package lse

func BumpFeed(st *FeedState, ev LeaseEvent) (uint64, bool) {
	return bump_v(st, ev)
}

func bump_v(st *FeedState, ev LeaseEvent) (uint64, bool) {
	if ev.Kind == "G" {
		st.Epoch++
		st.Fence++
		if st.ActivePref == nil {
			st.ActivePref = map[string]bool{}
		}
		st.ActivePref[ev.Prefix] = true
		if ev.Seq > st.LastSeq {
			st.LastSeq = ev.Seq
		}
		return st.Epoch, true
	}
	if ev.Kind == "W" {
		if ev.Seq > st.LastSeq {
			st.LastSeq = ev.Seq
		}
		return st.Epoch, false
	}
	return st.Epoch, false
}
