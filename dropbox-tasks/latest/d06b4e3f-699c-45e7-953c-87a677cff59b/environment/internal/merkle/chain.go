package merkle

import (
	"crypto/sha256"
	"encoding/binary"
)

// FoldCheckpoint extends a stream's tip hash chain with one more checkpoint.
// prevTip is Genesis(streamID) before the stream's first checkpoint, and the
// previous call's return value for every checkpoint after that, so the final
// tip summarizes every checkpoint the stream has ever had, in order. Folding
// depends only on checkpoint bookkeeping (never on raw event rows), which is
// what lets chain_tip_hash stay identical before and after events belonging
// to already-checkpointed batches are pruned away.
func FoldCheckpoint(prevTip [32]byte, batchIndex, startSeq, endSeq int64, merkleRoot [32]byte, keyID string) [32]byte {
	buf := make([]byte, 0, 1+32+8+8+8+32+2+len(keyID))
	buf = append(buf, TipPrefix)
	buf = append(buf, prevTip[:]...)
	buf = appendBE64(buf, uint64(batchIndex))
	buf = appendBE64(buf, uint64(startSeq))
	buf = appendBE64(buf, uint64(endSeq))
	buf = append(buf, merkleRoot[:]...)

	var keyLen [2]byte
	binary.BigEndian.PutUint16(keyLen[:], uint16(len(keyID)))
	buf = append(buf, keyLen[:]...)
	buf = append(buf, []byte(keyID)...)

	return sha256.Sum256(buf)
}

func appendBE64(buf []byte, v uint64) []byte {
	var b [8]byte
	binary.BigEndian.PutUint64(b[:], v)
	return append(buf, b[:]...)
}
