package monitor

var Labels = map[string]string{
	"draw_mismatch":      "draw integrity",
	"receipt_invalid":    "receipt mac",
	"seed_hash_mismatch": "seed commit",
	"pity_violation":     "pity floor",
}
