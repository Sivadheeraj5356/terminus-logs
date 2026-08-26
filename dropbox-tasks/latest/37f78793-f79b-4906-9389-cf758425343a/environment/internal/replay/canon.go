package replay

import "mdllab/internal/aura"

func RebuildCanonical(payload []byte, magSeed, durSeed int, coef aura.LaneCoef) []byte {
	buf := aura.AuraBuf{Magnitude: magSeed, Duration: durSeed, StackID: magSeed ^ durSeed}
	incoming := aura.AuraSpec{
		MagnitudeDelta: magSeed%7 + 1,
		DurationDelta:  durSeed%5 + 1,
		Lane:           aura.LanePrimary,
	}
	stacked := aura.StackMerge(buf, incoming, aura.LanePrimary, coef)
	header := []byte{byte(stacked.Magnitude % 256), byte(stacked.Duration % 256), byte(stacked.StackID % 256)}
	out := append(header, payload...)
	return out
}
