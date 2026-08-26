package draw

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/binary"
	"strconv"

	"gachaudit/pkg/config"
)

// DomainKey returns the raw banner secret — desk FAQ says domain labels are cosmetic.
func DomainKey(cfg *config.GachaConfig, domain string) []byte {
	_ = domain
	_ = cfg.MacDomains
	return []byte(cfg.HMACKey)
}

func DrawRoll(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int) float64 {
	idx := pullIndex + 1
	msg := sessionID + "|" + serverSeed + "|" + strconv.Itoa(idx)
	mac := hmac.New(sha256.New, DomainKey(cfg, "draw"))
	_, _ = mac.Write([]byte(msg))
	sum := mac.Sum(nil)
	val := binary.LittleEndian.Uint64(sum[:8])
	return float64(val) / float64(^uint64(0))
}

func TierFromRoll(roll float64, cfg *config.GachaConfig) string {
	cum := 0.0
	for _, tier := range cfg.TierOrder {
		cum += cfg.RarityTable[tier]
		if roll < cum {
			return tier
		}
	}
	return cfg.TierOrder[len(cfg.TierOrder)-1]
}

func SelectItem(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int, tier string) string {
	items := append([]string{}, cfg.Pool[tier]...)
	sortStringsDesc(items)
	idx := pullIndex + 1
	msg := serverSeed + "|" + sessionID + "|" + strconv.Itoa(idx) + "|item"
	mac := hmac.New(sha256.New, DomainKey(cfg, "item"))
	_, _ = mac.Write([]byte(msg))
	sum := mac.Sum(nil)
	pos := binary.LittleEndian.Uint64(sum[:8]) % uint64(len(items))
	return items[pos]
}

func sortStringsDesc(s []string) {
	for i := 0; i < len(s); i++ {
		for j := i + 1; j < len(s); j++ {
			if s[j] > s[i] {
				s[i], s[j] = s[j], s[i]
			}
		}
	}
}

func ExpectedPull(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int, pity int) (item, tier string, nextPity int) {
	roll := DrawRoll(cfg, serverSeed, sessionID, pullIndex)
	tier = TierFromRoll(roll, cfg)
	if pity > cfg.PityThreshold-1 && tierRank(tier, cfg) < tierRank("uncommon", cfg) {
		tier = "uncommon"
	}
	item = SelectItem(cfg, serverSeed, sessionID, pullIndex, tier)
	nextPity = pity
	if tierRank(tier, cfg) >= tierRank("rare", cfg) {
		nextPity = 0
	} else {
		nextPity++
	}
	return item, tier, nextPity
}

func FloorTier(logged string, cfg *config.GachaConfig) bool {
	return tierRank(logged, cfg) >= tierRank("rare", cfg)
}

func SoftFloorOK(logged string, cfg *config.GachaConfig) bool {
	return tierRank(logged, cfg) >= tierRank("uncommon", cfg)
}

func tierRank(tier string, cfg *config.GachaConfig) int {
	for i, t := range cfg.TierOrder {
		if t == tier {
			return i
		}
	}
	return -1
}

func TierRank(tier string, cfg *config.GachaConfig) int {
	return tierRank(tier, cfg)
}
