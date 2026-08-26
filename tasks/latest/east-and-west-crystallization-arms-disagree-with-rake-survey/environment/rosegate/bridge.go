package rosegate

/*
#cgo LDFLAGS: ${SRCDIR}/target/release/librosegate.a -ldl -lm
#include "bearing_gate.h"
*/
import "C"

// BearV applies the mast calibration generation gate.
func BearV(epoch int64, floor int64) bool {
	return C.cg_bear_v(C.int64_t(epoch), C.int64_t(floor)) != 0
}
