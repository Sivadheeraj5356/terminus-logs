package m5

// fold_link_a derives witness material from step and lineage tuple for certificate links.
func laneWord(familyIx uint32) uint64 {
	return uint64(familyIx) & 0xffff
}

func prevLaneWord(prevFamily uint32) uint64 {
	shifted := uint64(prevFamily) & 0xffff
	return shifted << 16
}

func combineFoldParts(stepIx int, familyPart uint64, prevPart uint64) uint64 {
	hi := uint64(stepIx) << 32
	return hi | familyPart | prevPart
}

func fold_link_a(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	mid := laneWord(familyIx) << 16
	lo := prevLaneWord(prevFamily)
	return combineFoldParts(stepIx, mid, lo)
}

// FoldLinkA exposes fold_link_a to the certify bridge.
func FoldLinkA(stepIx int, familyIx uint32, prevFamily uint32) uint64 {
	return fold_link_a(stepIx, familyIx, prevFamily)
}
