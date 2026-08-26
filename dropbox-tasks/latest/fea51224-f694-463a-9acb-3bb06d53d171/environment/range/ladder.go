package rangepkg

import "slotmgr/internal/policy"

func stride_lane(base int, ord int, peers int, root string) int {
	pol := policy.Load(root)
	if pol.LanePerPeerStride {
		return base + ord/peers
	}
	return base + ord
}

func LadderTick(base int, ord int, peers int, root string) int {
	return stride_lane(base, ord, peers, root)
}

func LaneStride(base int, ord int, peers int, root string) int {
	return stride_lane(base, ord, peers, root)
}
