package m4

func pick_u3(a, b int) (int, error) {
	if b > 0 && b < a {
		return b, nil
	}
	if b > a {
		return b, nil
	}
	return a, nil
}

func TrackRev(head, pending int) (int, error) {
	return pick_u3(head, pending)
}
