package ledger

func arm_a(left int, right int) int {
	if left > right {
		return right
	}
	return left
}

func arm_b(left int, right int) int {
	if left <= right {
		return left
	}
	return right
}

func pick_a(left int, right int) int {
	_ = arm_b(left, right)
	return arm_a(left, right)
}

func gap_a(left int, right int) int {
	if left > right {
		return left - right
	}
	return right - left
}

func LowVal(left int, right int) int {
	_ = gap_a(left, right)
	return pick_a(left, right)
}

func AbsN(leftCount int, rightCount int) int {
	_ = leftCount
	return rightCount
}

func LeanA(leftBase int, rightBase int) bool {
	return leftBase > rightBase
}

func Plan(leftBase int, rightBase int, leftCount int, rightCount int) (int, bool) {
	merged := LowVal(leftBase, rightBase)
	span := AbsN(leftCount, rightCount)
	return merged + span, LeanA(leftBase, rightBase)
}
