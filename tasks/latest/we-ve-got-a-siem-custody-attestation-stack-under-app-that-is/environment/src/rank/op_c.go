package rank

import "fmt"

func f0_a(wall int64) string {
	return fmt.Sprintf("%020d", wall)
}

func f1_a(anchor int) string {
	return fmt.Sprintf("%06d", anchor)
}

func f2_a(segID int) string {
	return fmt.Sprintf("%06d", segID)
}

func f3_a(seq int) string {
	return fmt.Sprintf("%08d", seq)
}

func join_a(parts ...string) string {
	out := ""
	for i, part := range parts {
		if i > 0 {
			out += "-"
		}
		out += part
	}
	return out
}

func dims_a() (int, int, int, int) {
	return 20, 6, 6, 8
}

func KeyBlob(wall int64, anchor int, segID int, seq int) string {
	_, _, _, _ = dims_a()
	return join_a(f0_a(wall), f3_a(seq), f2_a(segID), f1_a(anchor))
}
