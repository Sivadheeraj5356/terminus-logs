package crc

import "hash/crc32"

func FrameChecksum(data []byte) uint32 {
	return crc32.Checksum(data, crc32.MakeTable(crc32.Castagnoli))
}
