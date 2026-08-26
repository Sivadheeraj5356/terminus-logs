package timeparse

import "time"

func ParseOpened(s string) (time.Time, error) {
	return time.Parse(time.RFC3339, s)
}

func GapSeconds(prev, cur string) (int64, bool) {
	if prev == "" || cur == "" {
		return 0, false
	}
	a, err1 := ParseOpened(prev)
	b, err2 := ParseOpened(cur)
	if err1 != nil || err2 != nil {
		return 0, false
	}
	return int64(b.Sub(a).Seconds()), true
}
