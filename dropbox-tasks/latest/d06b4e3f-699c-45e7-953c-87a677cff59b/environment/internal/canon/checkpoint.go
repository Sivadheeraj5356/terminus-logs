package canon

// CheckpointSigningBytes returns the exact byte sequence that gets
// HMAC-signed, and later re-verified, for one checkpoint batch. Binding the
// stream id and batch coordinates into the signed bytes -- not just the bare
// Merkle root -- stops a signature computed for one batch from also
// validating a different batch, or a different stream, that happens to
// produce the same root.
func CheckpointSigningBytes(streamID string, batchIndex, startSeq, endSeq int64, merkleRoot [32]byte) []byte {
	buf := make([]byte, 0, 24+2+len(streamID)+32)
	buf = append(buf, []byte("CHAINAUDIT-CKPT-v1")...)
	buf = appendLP16(buf, []byte(streamID))
	buf = appendBE64(buf, uint64(batchIndex))
	buf = appendBE64(buf, uint64(startSeq))
	buf = appendBE64(buf, uint64(endSeq))
	buf = append(buf, merkleRoot[:]...)
	return buf
}
