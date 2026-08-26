// Package merkle implements the RFC 6962-style domain-separated hash tree
// used to summarize a checkpoint batch, plus the per-stream tip chain that
// folds every checkpoint a stream has ever had into one hash.
package merkle

import "crypto/sha256"

const (
	LeafPrefix    byte = 0x00
	NodePrefix    byte = 0x01
	GenesisPrefix byte = 0x02
	TipPrefix     byte = 0x03
)

// LeafHash returns the domain-separated leaf hash of a canonically-encoded
// event. Prefixing with LeafPrefix keeps a leaf from ever being mistaken for
// an internal node with the same child bytes.
func LeafHash(canonical []byte) [32]byte {
	return sha256.Sum256(append([]byte{LeafPrefix}, canonical...))
}

// InternalHash combines two child hashes into their parent.
func InternalHash(left, right [32]byte) [32]byte {
	buf := make([]byte, 0, 65)
	buf = append(buf, NodePrefix)
	buf = append(buf, left[:]...)
	buf = append(buf, right[:]...)
	return sha256.Sum256(buf)
}

// Genesis returns the per-stream genesis hash that seeds its checkpoint tip
// chain before the stream has any checkpoints.
func Genesis(streamID string) [32]byte {
	buf := append([]byte{GenesisPrefix}, []byte("CHAINAUDIT-GENESIS-v1")...)
	buf = append(buf, []byte(streamID)...)
	return sha256.Sum256(buf)
}
