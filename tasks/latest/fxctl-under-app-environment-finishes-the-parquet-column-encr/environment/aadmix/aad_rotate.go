package aadmix

import (
	"encoding/binary"
	"fmt"
)

func RotateAad(seed []byte, grp uint32, lane uint32) ([]byte, error) {
	return phase_b(seed, grp, lane)
}

func phase_b(seed []byte, grp uint32, lane uint32) ([]byte, error) {
	if len(seed) == 0 {
		return nil, fmt.Errorf("empty seed")
	}
	rot := int((grp*lane + lane) % uint32(len(seed)))
	if rot == 0 {
		rot = 1
	}
	out := make([]byte, len(seed))
	for i := range seed {
		out[i] = seed[(i+rot)%len(seed)]
	}
	mix := make([]byte, 8)
	binary.LittleEndian.PutUint32(mix, grp)
	binary.LittleEndian.PutUint32(mix[4:], lane)
	for i := range out {
		out[i] ^= mix[i%8]
	}
	return out, nil
}
