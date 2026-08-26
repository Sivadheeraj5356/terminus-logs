package clock

import "strconv"

func ParseWallToken(raw string) (int64, error) {
	return strconv.ParseInt(raw, 10, 64)
}

func WallCeil(sec int64, step int64) int64 {
	if step <= 0 {
		return sec
	}
	rem := sec % step
	if rem == 0 {
		return sec
	}
	return sec + (step - rem)
}
