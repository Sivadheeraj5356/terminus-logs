package reg

func ClassOf(r RowRec, tags map[string]uint8) uint8 {
	if c, ok := tags[r.Key]; ok && c != 0 {
		return c
	}
	return r.Class
}
