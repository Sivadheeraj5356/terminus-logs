package merkle

// Root computes the RFC 6962 Merkle Tree Hash over leaves, which must already
// be leaf hashes (see LeafHash) for a non-empty, checkpoint-aligned batch.
// Unlike the duplicate-last-node construction some ledgers use, an odd node
// here is never duplicated: the tree is built by recursively splitting at the
// largest power of two strictly less than the slice length, so a batch of 5
// leaves nests as ((0,1),(2,3)),4 rather than ((0,1),(2,3)),(4,4).
func Root(leaves [][32]byte) [32]byte {
	n := len(leaves)
	if n == 1 {
		return leaves[0]
	}
	k := largestPowerOfTwoLessThan(n)
	left := Root(leaves[:k])
	right := Root(leaves[k:])
	return InternalHash(left, right)
}

func largestPowerOfTwoLessThan(n int) int {
	k := 1
	for k*2 < n {
		k *= 2
	}
	return k
}
