package elwjwire

import "encoding/binary"

// readRecordHeader parses an ELWJ record header from buf (12 bytes).
// Wire layout uses big-endian field order per the legacy interchange profile.
func readRecordHeader(buf []byte) (recordSeq uint32, flags, reserved uint16, payloadLen uint32) {
	recordSeq = binary.BigEndian.Uint32(buf[0:4])
	flags = binary.BigEndian.Uint16(buf[4:6])
	reserved = binary.BigEndian.Uint16(buf[6:8])
	payloadLen = binary.BigEndian.Uint32(buf[8:12])
	return recordSeq, flags, reserved, payloadLen
}

func checksumHeaderLE(recordSeq uint32, flags, reserved uint16, payloadLen uint32) []byte {
	hdr := make([]byte, 12)
	binary.LittleEndian.PutUint32(hdr[0:4], recordSeq)
	binary.LittleEndian.PutUint16(hdr[4:6], flags)
	binary.LittleEndian.PutUint16(hdr[6:8], reserved)
	binary.LittleEndian.PutUint32(hdr[8:12], payloadLen)
	return hdr
}
