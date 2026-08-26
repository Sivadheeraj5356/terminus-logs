package state

const (
	offset64 = 0xcbf29ce484222325
	prime64  = 0x100000001b3
)

func FNV1a64(data []byte) uint64 {
	h := uint64(offset64)
	for _, b := range data {
		h ^= uint64(b)
		h *= prime64
	}
	return h
}

func InputHash(parts ...[]byte) string {
	var all []byte
	for _, p := range parts {
		all = append(all, p...)
	}
	return fmtHex16(FNV1a64(all))
}

func fmtHex16(v uint64) string {
	const hexdigits = "0123456789abcdef"
	out := make([]byte, 16)
	for i := 15; i >= 0; i-- {
		out[i] = hexdigits[v&0xf]
		v >>= 4
	}
	return string(out)
}
