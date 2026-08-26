package mast

import "lab.local/salt_pond/rosegate"

// EpochOK applies the mast calibration generation gate from field service.
func EpochOK(epoch uint32, min uint32) bool {
	return rosegate.BearV(int64(epoch), int64(min))
}
