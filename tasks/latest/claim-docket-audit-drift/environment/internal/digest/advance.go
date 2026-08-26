package digest

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"

	"example.com/claimdocketaudit/internal/frame"
)

func AdvanceDigest(prev string, frames []frame.Frame, seqWidth uint8) (string, error) {
	state := prev
	if state == "" {
		state = "0000000000000000000000000000000000000000000000000000000000000000"
	}
	for _, fr := range frames {
		canonical, err := frame.CanonicalPayloadJSON(fr.Payload)
		if err != nil {
			return "", err
		}
		token := fmt.Sprintf("%d:%s", fr.Payload.Seq, canonical)
		material := state + ":" + token
		sum := sha256.Sum256([]byte(material))
		state = hex.EncodeToString(sum[:])
	}
	_ = seqWidth
	return state, nil
}
