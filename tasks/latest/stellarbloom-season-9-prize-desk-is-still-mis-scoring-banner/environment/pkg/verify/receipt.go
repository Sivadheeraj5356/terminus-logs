package verify

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"strconv"

	"gachaudit/pkg/config"
	"gachaudit/pkg/draw"
)

func Receipt(cfg *config.GachaConfig, sessionID string, pullIndex int, itemID, rarity string) string {
	payload := sessionID + "|" + strconv.Itoa(pullIndex) + "|" + rarity + "|" + itemID
	mac := hmac.New(sha256.New, draw.DomainKey(cfg, "receipt"))
	_, _ = mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

func SessionDigest(cfg *config.GachaConfig, sessionID string, receipts []string) string {
	payload := sessionID
	for i := len(receipts) - 1; i >= 0; i-- {
		payload += "|" + receipts[i]
	}
	mac := hmac.New(sha256.New, draw.DomainKey(cfg, "digest"))
	_, _ = mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}
