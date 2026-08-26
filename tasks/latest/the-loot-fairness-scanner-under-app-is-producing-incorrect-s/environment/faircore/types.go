package faircore

import (
	"encoding/json"
	"os"
)

type PoolItem struct {
	ItemID   string `json:"item_id"`
	Tier     string `json:"tier"`
	Weight   int    `json:"weight"`
	Unique   bool   `json:"unique"`
	Cooldown int    `json:"cooldown"`
}

type Roll struct {
	Seq       int     `json:"seq"`
	PlayerID  string  `json:"player_id"`
	RollValue float64 `json:"roll_value"`
	ItemID    string  `json:"item_id"`
	Tier      string  `json:"tier"`
}

type Session struct {
	SessionID     string     `json:"session_id"`
	RNGSeed       int        `json:"rng_seed"`
	PityThreshold int        `json:"pity_threshold"`
	PityTier      string     `json:"pity_tier"`
	LootPool      []PoolItem `json:"loot_pool"`
	Rolls         []Roll     `json:"rolls"`
}

type TierStat struct {
	Tier      string  `json:"tier"`
	Observed  int     `json:"observed"`
	Expected  float64 `json:"expected"`
	ChiSquare float64 `json:"chi_square"`
}

type PlayerStat struct {
	PlayerID   string `json:"player_id"`
	EpicDrops  int    `json:"epic_drops"`
	TotalRolls int    `json:"total_rolls"`
}

type Finding struct {
	FindingID string `json:"finding_id"`
	PlayerID  string `json:"player_id"`
	Kind      string `json:"kind"`
	Detail    string `json:"detail"`
	Seq       int    `json:"seq"`
}

type SessionOut struct {
	SessionID       string       `json:"session_id"`
	Status          string       `json:"status"`
	GiniCoefficient float64      `json:"gini_coefficient"`
	TierStats       []TierStat   `json:"tier_stats"`
	Players         []PlayerStat `json:"players"`
	Findings        []Finding    `json:"findings"`
}

type Report struct {
	Sessions []SessionOut `json:"sessions"`
}

func LoadSession(path string) (Session, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return Session{}, err
	}
	var s Session
	if err := json.Unmarshal(raw, &s); err != nil {
		return Session{}, err
	}
	return s, nil
}
