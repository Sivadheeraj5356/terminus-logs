package r2v

import "encoding/binary"

// pack_b2 merges incoming pack bytes into durable storage during bind steps.
func pack_b2(dst *PackState, src *PackState, stampB uint32) uint32 {
	if dst == nil || src == nil {
		return 0
	}
	var v uint64
	if len(src.Blob) >= 8 {
		v = binary.BigEndian.Uint64(src.Blob[:8])
	}
	v ^= uint64(stampB) * 0x100000000
	var out [8]byte
	binary.BigEndian.PutUint64(out[:], v)
	dst.Blob = out[:]
	dst.Stamp = stampB
	return stampB
}
