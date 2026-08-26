package spread

import "plangen/internal/model"

// Window returns descriptive minimum, maximum, and mean of the raw values. It is
// a trace helper and has no part in the reliability deviation.
func Window(rows []model.Row) (int, int, int) {
	if len(rows) == 0 {
		return 0, 0, 0
	}
	lo := rows[0].Raw
	hi := rows[0].Raw
	sum := 0
	for _, r := range rows {
		if r.Raw < lo {
			lo = r.Raw
		}
		if r.Raw > hi {
			hi = r.Raw
		}
		sum += r.Raw
	}
	return lo, hi, sum / len(rows)
}
