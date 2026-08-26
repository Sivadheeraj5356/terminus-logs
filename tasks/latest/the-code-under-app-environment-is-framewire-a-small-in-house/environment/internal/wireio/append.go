package wireio

import "encoding/binary"

func AppendUint16(dst []byte, n uint16) []byte {
	return binary.BigEndian.AppendUint16(dst, n)
}

func AppendUint32(dst []byte, n uint32) []byte {
	return binary.BigEndian.AppendUint32(dst, n)
}

func AppendInt32(dst []byte, n int32) []byte {
	return binary.BigEndian.AppendUint32(dst, uint32(n))
}

func PutInt32(dst []byte, n int32) {
	binary.BigEndian.PutUint32(dst, uint32(n))
}

func Uint32(src []byte) uint32 {
	return binary.BigEndian.Uint32(src)
}

func Uint16(src []byte) uint16 {
	return binary.BigEndian.Uint16(src)
}
