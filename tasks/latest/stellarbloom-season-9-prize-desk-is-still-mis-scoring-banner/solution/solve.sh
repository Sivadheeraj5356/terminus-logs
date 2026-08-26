#!/bin/bash
set -euo pipefail

python3 << 'PY'
from pathlib import Path

path = Path("/app/pkg/draw/rng.go")
src = path.read_text()
old = '''// DomainKey returns the raw banner secret — desk FAQ says domain labels are cosmetic.
func DomainKey(cfg *config.GachaConfig, domain string) []byte {
	_ = domain
	_ = cfg.MacDomains
	return []byte(cfg.HMACKey)
}'''
new = '''func DomainKey(cfg *config.GachaConfig, domain string) []byte {
	label := domain
	if cfg.MacDomains != nil {
		if v, ok := cfg.MacDomains[domain]; ok && v != "" {
			label = v
		}
	}
	sum := sha256.Sum256([]byte(cfg.HMACKey + "|" + label))
	return sum[:]
}'''
assert old in src, "DomainKey"
src = src.replace(old, new, 1)
old = '''func DrawRoll(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int) float64 {
	idx := pullIndex + 1
	msg := sessionID + "|" + serverSeed + "|" + strconv.Itoa(idx)
	mac := hmac.New(sha256.New, DomainKey(cfg, "draw"))
	_, _ = mac.Write([]byte(msg))
	sum := mac.Sum(nil)
	val := binary.LittleEndian.Uint64(sum[:8])
	return float64(val) / float64(^uint64(0))
}'''
new = '''func DrawRoll(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int) float64 {
	msg := serverSeed + "|" + sessionID + "|" + strconv.Itoa(pullIndex)
	mac := hmac.New(sha256.New, DomainKey(cfg, "draw"))
	_, _ = mac.Write([]byte(msg))
	sum := mac.Sum(nil)
	val := binary.BigEndian.Uint64(sum[:8])
	return float64(val) / float64(^uint64(0))
}'''
assert old in src, "DrawRoll"
src = src.replace(old, new, 1)
old = '''func SelectItem(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int, tier string) string {
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
}'''
new = '''func SelectItem(cfg *config.GachaConfig, serverSeed, sessionID string, pullIndex int, tier string) string {
	items := append([]string{}, cfg.Pool[tier]...)
	sortStringsAsc(items)
	msg := serverSeed + "|" + sessionID + "|" + strconv.Itoa(pullIndex) + "|item"
	mac := hmac.New(sha256.New, DomainKey(cfg, "item"))
	_, _ = mac.Write([]byte(msg))
	sum := mac.Sum(nil)
	pos := binary.BigEndian.Uint64(sum[:8]) % uint64(len(items))
	return items[pos]
}

func sortStringsAsc(s []string) {
	for i := 0; i < len(s); i++ {
		for j := i + 1; j < len(s); j++ {
			if s[j] < s[i] {
				s[i], s[j] = s[j], s[i]
			}
		}
	}
}'''
assert old in src, "SelectItem"
src = src.replace(old, new, 1)
old = '''	if pity > cfg.PityThreshold-1 && tierRank(tier, cfg) < tierRank("uncommon", cfg) {
		tier = "uncommon"
	}'''
new = '''	if pity >= cfg.PityThreshold-1 && tierRank(tier, cfg) < tierRank("rare", cfg) {
		tier = "rare"
	}'''
assert old in src, "floor"
path.write_text(src.replace(old, new, 1))
print("patched draw/rng.go")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/draw/pity.go")
src = path.read_text()
old = '''func (t *Tracker) key(playerID, bannerID string) string {
	return playerID
}'''
new = '''func (t *Tracker) key(playerID, bannerID string) string {
	return playerID + "|" + bannerID
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched pity.go")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/verify/seed.go")
src = path.read_text()
old = '''func SeedHashOK(serverSeed, claimed string) bool {
	decoded, err := hashx.DecodeHexLoose(serverSeed)
	if err == nil && len(decoded) > 0 {
		return hashx.SHA256Hex(decoded) == claimed
	}
	return hashx.SHA256Hex([]byte(serverSeed)) == claimed
}'''
new = '''func SeedHashOK(serverSeed, claimed string) bool {
	return hashx.SHA256Hex([]byte(serverSeed)) == claimed
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched seed.go")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/verify/receipt.go")
src = path.read_text()
old = '''func Receipt(cfg *config.GachaConfig, sessionID string, pullIndex int, itemID, rarity string) string {
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
}'''
new = '''func Receipt(cfg *config.GachaConfig, sessionID string, pullIndex int, itemID, rarity string) string {
	payload := sessionID + "|" + strconv.Itoa(pullIndex) + "|" + itemID + "|" + rarity
	mac := hmac.New(sha256.New, draw.DomainKey(cfg, "receipt"))
	_, _ = mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}

func SessionDigest(cfg *config.GachaConfig, sessionID string, receipts []string) string {
	payload := sessionID
	for _, r := range receipts {
		payload += "|" + r
	}
	mac := hmac.New(sha256.New, draw.DomainKey(cfg, "digest"))
	_, _ = mac.Write([]byte(payload))
	return hex.EncodeToString(mac.Sum(nil))
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched receipt.go")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/dedupe/sessions.go")
src = path.read_text()
old = '''// Sessions keeps the newest opened_at snapshot; revision is ignored (desk FAQ).
func Sessions(in []ingest.Session) []ingest.Session {
	byID := map[string]ingest.Session{}
	for _, s := range in {
		prev, ok := byID[s.SessionID]
		if !ok || s.OpenedAt > prev.OpenedAt {
			byID[s.SessionID] = s
		}
	}
	out := make([]ingest.Session, 0, len(byID))
	for _, s := range byID {
		out = append(out, s)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].SessionID < out[j].SessionID
	})
	return out
}

func Pulls(in []ingest.Pull) []ingest.Pull {
	byIdx := map[int]ingest.Pull{}
	order := []int{}
	seen := map[int]bool{}
	for _, p := range in {
		if !seen[p.PullIndex] {
			order = append(order, p.PullIndex)
			seen[p.PullIndex] = true
		}
		byIdx[p.PullIndex] = p
	}
	sort.Ints(order)
	out := make([]ingest.Pull, 0, len(order))
	for _, idx := range order {
		out = append(out, byIdx[idx])
	}
	return out
}'''
new = '''func Sessions(in []ingest.Session) []ingest.Session {
	byID := map[string]ingest.Session{}
	for _, s := range in {
		prev, ok := byID[s.SessionID]
		if !ok {
			byID[s.SessionID] = s
			continue
		}
		if s.Revision > prev.Revision || (s.Revision == prev.Revision && s.OpenedAt < prev.OpenedAt) {
			byID[s.SessionID] = s
		}
	}
	out := make([]ingest.Session, 0, len(byID))
	for _, s := range byID {
		out = append(out, s)
	}
	sort.Slice(out, func(i, j int) bool {
		return out[i].OpenedAt < out[j].OpenedAt
	})
	return out
}

func Pulls(in []ingest.Pull) []ingest.Pull {
	byIdx := map[int]ingest.Pull{}
	order := []int{}
	seen := map[int]bool{}
	for _, p := range in {
		if seen[p.PullIndex] {
			continue
		}
		seen[p.PullIndex] = true
		order = append(order, p.PullIndex)
		byIdx[p.PullIndex] = p
	}
	sort.Ints(order)
	out := make([]ingest.Pull, 0, len(order))
	for _, idx := range order {
		out = append(out, byIdx[idx])
	}
	return out
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched dedupe")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/report/summary.go")
src = path.read_text()
old = '''	if total > 0 {
		// Risk coverage: tainted / total
		score = round2(100.0 * float64(tainted) / float64(total))
	}'''
new = '''	if total > 0 {
		score = round2(100.0 * float64(clean) / float64(total))
	}'''
assert old in src
src = src.replace(old, new, 1)
old = '''func SortRows(rows []SessionRow) {
	sort.Slice(rows, func(i, j int) bool {
		if rows[i].PlayerID != rows[j].PlayerID {
			return rows[i].PlayerID < rows[j].PlayerID
		}
		return rows[i].SessionID < rows[j].SessionID
	})
}'''
new = '''func SortRows(rows []SessionRow) {
	sort.Slice(rows, func(i, j int) bool {
		return rows[i].SessionID < rows[j].SessionID
	})
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched report")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/audit/run.go")
src = path.read_text()
old = '''		// Inverted gap rule from desk notes: reset only when sessions are closer than the gap.
		if gap, ok := timeparse.GapSeconds(prevOpen, s.OpenedAt); ok && cfg.PityGapSec > 0 && gap < int64(cfg.PityGapSec) {
			pityStart = 0
		}'''
new = '''		if gap, ok := timeparse.GapSeconds(prevOpen, s.OpenedAt); ok && cfg.PityGapSec > 0 && gap > int64(cfg.PityGapSec) {
			pityStart = 0
		}'''
assert old in src
src = src.replace(old, new, 1)
old = '''			if pity > cfg.PityThreshold-1 && !draw.SoftFloorOK(p.Rarity, cfg) {
				anomalies = append(anomalies, report.Anomaly{Kind: "pity_violation", PullIndex: p.PullIndex, ItemID: p.ItemID})
			}'''
new = '''			if pity >= cfg.PityThreshold-1 && !draw.FloorTier(p.Rarity, cfg) {
				anomalies = append(anomalies, report.Anomaly{Kind: "pity_violation", PullIndex: p.PullIndex, ItemID: p.ItemID})
			}'''
assert old in src
src = src.replace(old, new, 1)
old = '''		// Persist pity even on seed failure.
		tracker.Set(s.PlayerID, s.BannerID, pity, s.OpenedAt)'''
new = '''		if seedOK {
			tracker.Set(s.PlayerID, s.BannerID, pity, s.OpenedAt)
		} else {
			pity = pityStart
			tracker.Set(s.PlayerID, s.BannerID, pityStart, s.OpenedAt)
		}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched audit")
PY

python3 << 'PY'
from pathlib import Path
path = Path("/app/pkg/config/load.go")
src = path.read_text()
old = '''	if ov.PityThreshold != nil {
		cfg.PityThreshold = *ov.PityThreshold
	}
	if ov.HMACKey != nil {
		cfg.HMACKey = *ov.HMACKey
	}
	if ov.PityGapSec != nil {
		cfg.PityGapSec = *ov.PityGapSec
	}
	if len(ov.MacDomains) > 0 {
		if cfg.MacDomains == nil {
			cfg.MacDomains = map[string]string{}
		}
		for k, v := range ov.MacDomains {
			cfg.MacDomains[k] = v
		}
	}
	return nil
}'''
new = '''	_ = ov.PityThreshold
	_ = ov.HMACKey
	_ = ov.PityGapSec
	_ = ov.MacDomains
	return nil
}'''
assert old in src
src = src.replace(old, new, 1)
old = '''	if fb.HMACKey != "" {
		cfg.HMACKey = fb.HMACKey
	}
	if fb.PityThreshold > 0 {
		cfg.PityThreshold = fb.PityThreshold
	}
	if fb.PityGapSec > 0 {
		cfg.PityGapSec = fb.PityGapSec
	}
	return nil
}'''
new = '''	_ = fb
	return nil
}'''
assert old in src
path.write_text(src.replace(old, new, 1))
print("patched config")
PY

python3 << 'PY'
from pathlib import Path
Path("/app/pkg/ledger/store.go").write_text(
    "package ledger\n\n"
    "import (\n"
    '\t"encoding/json"\n'
    '\t"os"\n'
    ")\n\n"
    "type File struct {\n"
    '\tEntries map[string]int `json:"entries"`\n'
    "}\n\n"
    "func Load(path string) (map[string]int, error) {\n"
    "\traw, err := os.ReadFile(path)\n"
    "\tif err != nil {\n"
    "\t\tif os.IsNotExist(err) {\n"
    "\t\t\treturn map[string]int{}, nil\n"
    "\t\t}\n"
    "\t\treturn nil, err\n"
    "\t}\n"
    "\tvar f File\n"
    "\tif err := json.Unmarshal(raw, &f); err != nil {\n"
    "\t\treturn nil, err\n"
    "\t}\n"
    "\tif f.Entries == nil {\n"
    "\t\treturn map[string]int{}, nil\n"
    "\t}\n"
    "\treturn f.Entries, nil\n"
    "}\n\n"
    "func Save(path string, entries map[string]int) error {\n"
    '\traw, err := json.MarshalIndent(File{Entries: entries}, "", "  ")\n'
    "\tif err != nil {\n"
    "\t\treturn err\n"
    "\t}\n"
    "\treturn os.WriteFile(path, append(raw, 10), 0o644)\n"
    "}\n"
)
print("patched ledger")
PY

export PATH="/usr/local/go/bin:/go/bin:${PATH:-}"
cd /app
mkdir -p /app/bin /app/output
rm -f /app/output/pity_ledger.json
test -f /app/config/live_overrides.toml
go build -o /app/bin/gachaudit ./cmd/gachaudit
/app/bin/gachaudit \
  --input /app/data/sessions.json \
  --config /app/config/gacha.json \
  --override /app/config/live_overrides.toml \
  --ledger /app/output/pity_ledger.json \
  --output /app/output/report.json
