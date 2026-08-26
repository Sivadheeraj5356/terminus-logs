#!/usr/bin/env bash
set -euo pipefail

export GOROOT="${GOROOT:-/usr/local/go}"
export PATH="${GOROOT}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:${PATH:-}"
export GOTOOLCHAIN="${GOTOOLCHAIN:-local}"
export GOPROXY="${GOPROXY:-off}"
export GOFLAGS="${GOFLAGS:--mod=mod}"
export GOCACHE="${GOCACHE:-/tmp/go-cache}"
export HOME="${HOME:-/root}"

SRC_DIR="$(mktemp -d)"
BIN_PATH="/tmp/chunkstore_selector_bin"
mkdir -p /app/output

cat > "${SRC_DIR}/go.mod" <<'GOMOD'
module chunkstoreselector

go 1.24
GOMOD

cat > "${SRC_DIR}/main.go" <<'GOSRC'
package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type ChunkRow struct {
	ChunkId        string `json:"chunk_id"`
	ObjectId       string `json:"object_id"`
	RegisteredTsNs int64  `json:"registered_ts_ns"`
	SizeBytes      int64  `json:"size_bytes"`
	TenantId       string `json:"tenant_id"`
	Verdict        string `json:"verdict"`
}

type TenantStats struct {
	BytesDehydrated int64  `json:"bytes_dehydrated"`
	BytesKeptCanon  int64  `json:"bytes_kept_canonical"`
	ChunkCount      int    `json:"chunk_count"`
	TopVerdict      string `json:"top_verdict"`
}

type Summary struct {
	BytesDehydrated int64  `json:"bytes_dehydrated"`
	BytesKeptCanon  int64  `json:"bytes_kept_canonical"`
	ReportDigest    string `json:"report_digest"`
	RunTsNs         int64  `json:"run_ts_ns"`
	TotalChunks     int    `json:"total_chunks"`
}

type Output struct {
	ByTenant  map[string]TenantStats `json:"by_tenant"`
	ByVerdict map[string]int         `json:"by_verdict"`
	Chunks    []ChunkRow             `json:"chunks"`
	Summary   Summary                `json:"summary"`
}

type CanonicalEntry struct {
	Hash             string `json:"hash"`
	CanonicalChunkId string `json:"canonical_chunk_id"`
	OwnerTenant      string `json:"owner_tenant"`
	ContentFP        string `json:"content_fingerprint"`
	SizeBytes        int64  `json:"size_bytes"`
	FirstSeenTsNs    int64  `json:"first_seen_ts_ns"`
}

type CanonicalBook struct {
	Entries []CanonicalEntry `json:"entries"`
}

type StrikeRecord struct {
	TenantId     string `json:"tenant_id"`
	StrikeCount  int    `json:"strike_count"`
	LastStrikeNs int64  `json:"last_strike_ns"`
}

type StickyRule struct {
	TenantId            string `json:"tenant_id"`
	StickyThreshold     int    `json:"sticky_threshold"`
	ObservationWindowNs int64  `json:"observation_window_ns"`
}

var verdictSeverity = map[string]int{
	"VOIDED":                   19,
	"REJECTED_CONTRADICTORY":   18,
	"INVALID":                  17,
	"REJECTED_TYPE":            16,
	"REJECTED_SEAL":            15,
	"REJECTED_REPLAY":          14,
	"SCHEMA_DRIFT_QUARANTINED": 13,
	"QUARANTINED_TENANT":       12,
	"REJECTED_COLLISION":       11,
	"REJECTED_WEAK_HASH":       10,
	"REJECTED_DUPLICATE":       9,
	"DEFERRED_STALE":           8,
	"DEFERRED_COOLDOWN":        7,
	"DEFERRED_REHASH":          6,
	"DEFERRED_HOT":             5,
	"DEFERRED_BANDWIDTH":       4,
	"DEFERRED_RESERVED_OUT":    3,
	"DEHYDRATED":               2,
	"KEPT_CANONICAL":           1,
}

var allVerdicts = []string{
	"DEFERRED_BANDWIDTH", "DEFERRED_COOLDOWN", "DEFERRED_HOT",
	"DEFERRED_REHASH", "DEFERRED_RESERVED_OUT", "DEFERRED_STALE",
	"DEHYDRATED", "INVALID", "KEPT_CANONICAL", "QUARANTINED_TENANT",
	"REJECTED_COLLISION", "REJECTED_CONTRADICTORY", "REJECTED_DUPLICATE",
	"REJECTED_REPLAY", "REJECTED_SEAL", "REJECTED_TYPE", "REJECTED_WEAK_HASH",
	"SCHEMA_DRIFT_QUARANTINED", "VOIDED",
}

func readFile(p string) string {
	b, err := os.ReadFile(p)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read %s: %v\n", p, err)
		os.Exit(2)
	}
	return string(b)
}

func parseKVProps(p string) map[string]string {
	out := map[string]string{}
	for _, line := range strings.Split(readFile(p), "\n") {
		line = strings.TrimSpace(line)
		if line == "" || strings.HasPrefix(line, "#") || strings.HasPrefix(line, "[") {
			continue
		}
		idx := strings.IndexAny(line, "=:")
		if idx < 0 {
			continue
		}
		k := strings.TrimSpace(line[:idx])
		v := strings.TrimSpace(line[idx+1:])
		out[k] = v
	}
	return out
}

func mustInt64(s string) int64 {
	v, err := strconv.ParseInt(s, 10, 64)
	if err != nil {
		fmt.Fprintf(os.Stderr, "parse int %q: %v\n", s, err)
		os.Exit(2)
	}
	return v
}

func mustInt(s string) int {
	return int(mustInt64(s))
}

func computeSeal(secret, chunkID, tenant, hashv, fp, sizeRaw, tsRaw string) string {
	canonical := chunkID + "|" + tenant + "|" + hashv + "|" + fp + "|" + sizeRaw + "|" + tsRaw
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(canonical))
	return hex.EncodeToString(mac.Sum(nil))[:16]
}

func resolveAlias(tenant string, aliases map[string]string, tenantMap map[string]string, maxHops int) (string, bool) {
	visited := map[string]bool{}
	cur := tenant
	for hop := 0; hop <= maxHops; hop++ {
		if visited[cur] {
			return "", false
		}
		visited[cur] = true
		if _, ok := tenantMap[cur]; ok {
			return cur, true
		}
		next, hasAlias := aliases[cur]
		if !hasAlias {
			return "", false
		}
		cur = next
	}
	return "", false
}

func main() {
	dataRoot := "/app"

	runCfg := parseKVProps(filepath.Join(dataRoot, "cycle_witness", "run_config.properties"))
	freshCfg := parseKVProps(filepath.Join(dataRoot, "cycle_witness", "freshness.cfg"))
	hotCfg := parseKVProps(filepath.Join(dataRoot, "tier_dialer", "hot_threshold.ini"))
	weakCfg := parseKVProps(filepath.Join(dataRoot, "hash_codec", "weak_set.cfg"))
	strongCfg := parseKVProps(filepath.Join(dataRoot, "hash_codec", "strong_set.cfg"))
	hmacCfg := parseKVProps(filepath.Join(dataRoot, "hash_codec", "hmac_secret.cfg"))

	runTsNs := mustInt64(runCfg["run_ts_ns"])
	retentionWindowNs := mustInt64(runCfg["retention_window_ns"])
	wrapModulus := mustInt64(runCfg["refcount_wrap_modulus"])
	aliasMaxHops := mustInt(runCfg["alias_max_hops"])
	replayWindowNs := mustInt64(runCfg["replay_window_ns"])
	magnitudePivot := mustInt64(freshCfg["magnitude_pivot_ts_ns"])
	msToNsFactor := mustInt64(freshCfg["ms_to_ns_factor"])
	baseHotRefcount := mustInt(hotCfg["base_refcount"])
	weakReviewAfterNs := mustInt64(weakCfg["weak_review_after_ns"])
	strongReviewAfterNs := mustInt64(strongCfg["strong_review_after_ns"])
	secretKey := hmacCfg["secret_key"]

	weakAllowedTiersList := strings.Split(weakCfg["weak_allowed_tiers"], ",")
	weakAllowedTiers := map[string]bool{}
	for _, t := range weakAllowedTiersList {
		weakAllowedTiers[strings.TrimSpace(t)] = true
	}

	tierYaml := readFile(filepath.Join(dataRoot, "tier_dialer", "tier_caps.yaml"))
	multipliers := map[string]float64{}
	staleGrace := map[string]int64{}
	parseTierYaml(tierYaml, multipliers, staleGrace)

	algoToml := readFile(filepath.Join(dataRoot, "hash_codec", "algorithms.toml"))
	strongSet, weakSet := parseAlgorithmsToml(algoToml)

	canonBook := loadCanonicalBook(filepath.Join(dataRoot, "dedup_arena", "canonical_book.json"))
	canonByHash := map[string]CanonicalEntry{}
	for _, e := range canonBook.Entries {
		canonByHash[e.Hash] = e
	}

	tenantMap, _ := loadTenantMap(filepath.Join(dataRoot, "tenant_oracle", "tenant_map.psv"))
	tenantAliases := loadTenantAliases(filepath.Join(dataRoot, "tenant_oracle", "tenant_aliases.cfg"))

	stickyRules := loadStickyRules(filepath.Join(dataRoot, "quarantine_cell", "tenant_quarantine.jsonl"))
	strikes := loadStrikes(filepath.Join(dataRoot, "quarantine_cell", "strikes.ndjson"))

	stickyQuarantined := map[string]bool{}
	for tenant, sr := range strikes {
		rule, ok := stickyRules[tenant]
		if !ok {
			continue
		}
		if sr.StrikeCount >= rule.StickyThreshold && sr.LastStrikeNs+rule.ObservationWindowNs >= runTsNs {
			stickyQuarantined[tenant] = true
		}
	}

	refcountHistory := loadRefcountHistory(filepath.Join(dataRoot, "cycle_witness", "refcount_history.tsv"))

	replaySet := loadReplaySet(filepath.Join(dataRoot, "cycle_witness", "prior_cycle.jsonl"), runTsNs, replayWindowNs)
	cooldownActive := loadCooldownSet(filepath.Join(dataRoot, "quarantine_cell", "tenant_cooldown.jsonl"), runTsNs)

	type rawChunk struct {
		raw     []byte
		shard   string
		lineNum int
	}
	var rawLines []rawChunk

	shardDir := filepath.Join(dataRoot, "chunk_inbox")
	entries, err := os.ReadDir(shardDir)
	if err != nil {
		fmt.Fprintf(os.Stderr, "list shards: %v\n", err)
		os.Exit(2)
	}
	shardNames := []string{}
	for _, e := range entries {
		if !strings.HasSuffix(e.Name(), ".ndjson") {
			continue
		}
		shardNames = append(shardNames, e.Name())
	}
	sort.Strings(shardNames)
	for _, sn := range shardNames {
		body := readFile(filepath.Join(shardDir, sn))
		for i, ln := range strings.Split(body, "\n") {
			t := strings.TrimSpace(ln)
			if t == "" {
				continue
			}
			rawLines = append(rawLines, rawChunk{raw: []byte(t), shard: sn, lineNum: i + 1})
		}
	}

	type parsedChunk struct {
		chunkId         string
		objectId        string
		chunkOffset     int64
		sizeBytes       int64
		hash            string
		contentFP       string
		algorithm       string
		refcount        int64
		registeredTsNs  int64
		tier            string
		seal            string
		tenantCanonical string
		preVerdict      string
		rawSize         string
		rawTs           string
		rawTenant       string
		forceAdmit      bool
		forceReject     bool
		schemaVersion   int64
		hasSchemaVer    bool
		op              string
	}

	schemaCfg := parseKVProps(filepath.Join(dataRoot, "cycle_witness", "schema_versions.cfg"))
	supportedSchemas := map[int64]bool{}
	for _, s := range strings.Split(schemaCfg["supported_schemas"], ",") {
		s = strings.TrimSpace(s)
		if s == "" {
			continue
		}
		if n, err := strconv.ParseInt(s, 10, 64); err == nil {
			supportedSchemas[n] = true
		}
	}

	floatRe := regexp.MustCompile(`[.eE]`)

	parsed := []*parsedChunk{}
	for _, rc := range rawLines {
		pc := &parsedChunk{}
		var fields map[string]json.RawMessage
		if err := json.Unmarshal(rc.raw, &fields); err != nil {
			pc.chunkId = "<malformed>"
			pc.preVerdict = "INVALID"
			parsed = append(parsed, pc)
			continue
		}
		if v, ok := fields["chunk_id"]; ok {
			_ = json.Unmarshal(v, &pc.chunkId)
		}
		if v, ok := fields["object_id"]; ok {
			_ = json.Unmarshal(v, &pc.objectId)
		}
		if v, ok := fields["hash"]; ok {
			_ = json.Unmarshal(v, &pc.hash)
		}
		if v, ok := fields["content_fingerprint"]; ok {
			_ = json.Unmarshal(v, &pc.contentFP)
		}
		if v, ok := fields["algorithm"]; ok {
			_ = json.Unmarshal(v, &pc.algorithm)
		}
		if v, ok := fields["tier"]; ok {
			_ = json.Unmarshal(v, &pc.tier)
		}
		if v, ok := fields["seal"]; ok {
			_ = json.Unmarshal(v, &pc.seal)
		}
		if v, ok := fields["force_admit"]; ok {
			_ = json.Unmarshal(v, &pc.forceAdmit)
		}
		if v, ok := fields["force_reject"]; ok {
			_ = json.Unmarshal(v, &pc.forceReject)
		}
		if v, ok := fields["schema_version"]; ok {
			var n int64
			if err := json.Unmarshal(v, &n); err == nil {
				pc.schemaVersion = n
				pc.hasSchemaVer = true
			}
		}
		if v, ok := fields["op"]; ok {
			_ = json.Unmarshal(v, &pc.op)
		}

		if v, ok := fields["tenant_id"]; ok {
			_ = json.Unmarshal(v, &pc.rawTenant)
		}
		canon, resolved := resolveAlias(pc.rawTenant, tenantAliases, tenantMap, aliasMaxHops)
		if resolved {
			pc.tenantCanonical = canon
		}

		if pc.forceAdmit && pc.forceReject {
			pc.preVerdict = "REJECTED_CONTRADICTORY"
			parsed = append(parsed, pc)
			continue
		}
		if !resolved {
			pc.preVerdict = "INVALID"
			parsed = append(parsed, pc)
			continue
		}

		intFields := []string{"chunk_offset", "size_bytes", "refcount", "registered_ts"}
		typeBad := false
		for _, fn := range intFields {
			v, has := fields[fn]
			if !has {
				typeBad = true
				break
			}
			tok := strings.TrimSpace(string(v))
			inner := tok
			wasQuoted := false
			if len(inner) >= 2 && inner[0] == '"' && inner[len(inner)-1] == '"' {
				inner = inner[1 : len(inner)-1]
				wasQuoted = true
			}
			hasRadixPrefix := strings.HasPrefix(inner, "0x") || strings.HasPrefix(inner, "0X") ||
				strings.HasPrefix(inner, "0o") || strings.HasPrefix(inner, "0O") ||
				strings.HasPrefix(inner, "0b") || strings.HasPrefix(inner, "0B")
			if wasQuoted && !hasRadixPrefix {
				typeBad = true
				break
			}
			if floatRe.MatchString(inner) && !hasRadixPrefix {
				typeBad = true
				break
			}
			n, err := strconv.ParseInt(inner, 0, 64)
			if err != nil {
				typeBad = true
				break
			}
			switch fn {
			case "chunk_offset":
				pc.chunkOffset = n
			case "size_bytes":
				pc.sizeBytes = n
				pc.rawSize = inner
			case "refcount":
				pc.refcount = n
			case "registered_ts":
				pc.registeredTsNs = n
				pc.rawTs = inner
			}
		}
		if typeBad {
			pc.preVerdict = "REJECTED_TYPE"
			parsed = append(parsed, pc)
			continue
		}

		expectedSeal := computeSeal(secretKey, pc.chunkId, pc.rawTenant, pc.hash, pc.contentFP, pc.rawSize, pc.rawTs)
		if pc.seal != expectedSeal {
			pc.preVerdict = "REJECTED_SEAL"
			parsed = append(parsed, pc)
			continue
		}

		if pc.registeredTsNs < magnitudePivot {
			pc.registeredTsNs = pc.registeredTsNs * msToNsFactor
		}

		parsed = append(parsed, pc)
	}

	dupKey := map[string][]*parsedChunk{}
	for _, pc := range parsed {
		if pc.preVerdict != "" {
			continue
		}
		k := pc.objectId + "|" + strconv.FormatInt(pc.chunkOffset, 10)
		dupKey[k] = append(dupKey[k], pc)
	}
	duplicateLosers := map[*parsedChunk]bool{}
	for _, grp := range dupKey {
		if len(grp) <= 1 {
			continue
		}
		sort.SliceStable(grp, func(i, j int) bool {
			if grp[i].registeredTsNs != grp[j].registeredTsNs {
				return grp[i].registeredTsNs < grp[j].registeredTsNs
			}
			return grp[i].chunkId < grp[j].chunkId
		})
		for i := 1; i < len(grp); i++ {
			duplicateLosers[grp[i]] = true
		}
	}

	bwBudget := loadBandwidthBudget(filepath.Join(dataRoot, "tier_dialer", "bandwidth_table.json"))

	type stagedRow struct {
		pc        *parsedChunk
		row       ChunkRow
		tentative string
		isHashHit bool
		hashEntry CanonicalEntry
	}
	staged := []*stagedRow{}
	for _, pc := range parsed {
		row := ChunkRow{
			ChunkId:        pc.chunkId,
			ObjectId:       pc.objectId,
			RegisteredTsNs: pc.registeredTsNs,
			SizeBytes:      pc.sizeBytes,
			TenantId:       pc.tenantCanonical,
		}
		sr := &stagedRow{pc: pc, row: row}
		if pc.preVerdict != "" {
			sr.tentative = pc.preVerdict
			staged = append(staged, sr)
			continue
		}
		if replaySet[pc.chunkId] {
			sr.tentative = "REJECTED_REPLAY"
			staged = append(staged, sr)
			continue
		}
		if pc.hasSchemaVer && !supportedSchemas[pc.schemaVersion] {
			sr.tentative = "SCHEMA_DRIFT_QUARANTINED"
			staged = append(staged, sr)
			continue
		}
		if stickyQuarantined[pc.tenantCanonical] {
			sr.tentative = "QUARANTINED_TENANT"
			staged = append(staged, sr)
			continue
		}
		entry, hashKnown := canonByHash[pc.hash]
		if hashKnown {
			if entry.OwnerTenant != pc.tenantCanonical || entry.ContentFP != pc.contentFP {
				sr.tentative = "REJECTED_COLLISION"
				staged = append(staged, sr)
				continue
			}
		}
		_ = strongSet
		isWeak := weakSet[pc.algorithm]
		if isWeak {
			age := runTsNs - pc.registeredTsNs
			if !weakAllowedTiers[pc.tier] || age > weakReviewAfterNs {
				sr.tentative = "REJECTED_WEAK_HASH"
				staged = append(staged, sr)
				continue
			}
		}
		if duplicateLosers[pc] {
			sr.tentative = "REJECTED_DUPLICATE"
			staged = append(staged, sr)
			continue
		}
		mult := multipliers[pc.tier]
		grace := staleGrace[pc.tier]
		staleCutoff := runTsNs - retentionWindowNs - grace
		if pc.registeredTsNs < staleCutoff {
			sr.tentative = "DEFERRED_STALE"
			staged = append(staged, sr)
			continue
		}
		if cooldownActive[pc.tenantCanonical] {
			sr.tentative = "DEFERRED_COOLDOWN"
			staged = append(staged, sr)
			continue
		}
		if strongSet[pc.algorithm] {
			age := runTsNs - pc.registeredTsNs
			if age > strongReviewAfterNs {
				sr.tentative = "DEFERRED_REHASH"
				staged = append(staged, sr)
				continue
			}
		}
		effRefcount := pc.refcount
		histKey := pc.tenantCanonical + "|" + pc.objectId + "|" + strconv.FormatInt(pc.chunkOffset, 10)
		if prev, has := refcountHistory[histKey]; has && prev > pc.refcount {
			effRefcount = pc.refcount + wrapModulus - prev
		}
		hotThreshold := int64(float64(baseHotRefcount) * mult)
		if effRefcount > hotThreshold {
			sr.tentative = "DEFERRED_HOT"
			staged = append(staged, sr)
			continue
		}
		if hashKnown && entry.OwnerTenant == pc.tenantCanonical && entry.ContentFP == pc.contentFP {
			sr.tentative = "DEHYDRATED"
			sr.isHashHit = true
			sr.hashEntry = entry
		} else {
			sr.tentative = "KEPT_CANONICAL"
		}
		staged = append(staged, sr)
	}

	dehyByHash := map[string][]*stagedRow{}
	for _, sr := range staged {
		if sr.tentative == "DEHYDRATED" {
			dehyByHash[sr.pc.hash] = append(dehyByHash[sr.pc.hash], sr)
		}
	}
	for _, grp := range dehyByHash {
		if len(grp) <= 1 {
			continue
		}
		sort.SliceStable(grp, func(i, j int) bool {
			bi := float64(grp[i].pc.sizeBytes) * multipliers[grp[i].pc.tier]
			bj := float64(grp[j].pc.sizeBytes) * multipliers[grp[j].pc.tier]
			if bi != bj {
				return bi > bj
			}
			return grp[i].pc.chunkId < grp[j].pc.chunkId
		})
		for k := 1; k < len(grp); k++ {
			grp[k].tentative = "DEFERRED_RESERVED_OUT"
		}
	}

	type admissionCandidate struct {
		sr  *stagedRow
		idx int
	}
	admit := []admissionCandidate{}
	for i, sr := range staged {
		if sr.tentative == "DEHYDRATED" || sr.tentative == "KEPT_CANONICAL" {
			admit = append(admit, admissionCandidate{sr: sr, idx: i})
		}
	}
	sort.SliceStable(admit, func(i, j int) bool {
		if admit[i].sr.pc.registeredTsNs != admit[j].sr.pc.registeredTsNs {
			return admit[i].sr.pc.registeredTsNs < admit[j].sr.pc.registeredTsNs
		}
		return admit[i].sr.pc.chunkId < admit[j].sr.pc.chunkId
	})
	accBytes := map[string]int64{}
	for _, ac := range admit {
		key := ac.sr.pc.tenantCanonical + "|" + ac.sr.pc.tier
		budget, hasBudget := bwBudget[key]
		if hasBudget && budget >= 0 {
			if accBytes[key]+ac.sr.pc.sizeBytes > budget {
				ac.sr.tentative = "DEFERRED_BANDWIDTH"
				continue
			}
		}
		accBytes[key] += ac.sr.pc.sizeBytes
	}

	final := []ChunkRow{}
	for _, sr := range staged {
		sr.row.Verdict = sr.tentative
		final = append(final, sr.row)
	}

	voidSources := map[string]*parsedChunk{}
	for _, pc := range parsed {
		if pc.op == "void_next" {
			voidSources[pc.chunkId] = pc
		}
	}
	for _, src := range voidSources {
		var nextRow *ChunkRow
		for i := range final {
			r := &final[i]
			if r.TenantId != src.tenantCanonical {
				continue
			}
			if r.ChunkId <= src.chunkId {
				continue
			}
			if nextRow == nil || r.ChunkId < nextRow.ChunkId {
				nextRow = r
			}
		}
		if nextRow != nil {
			nextRow.Verdict = "VOIDED"
		}
	}

	sort.SliceStable(final, func(i, j int) bool {
		si := verdictSeverity[final[i].Verdict]
		sj := verdictSeverity[final[j].Verdict]
		if si != sj {
			return si > sj
		}
		return final[i].ChunkId < final[j].ChunkId
	})

	byVerdict := map[string]int{}
	for _, v := range allVerdicts {
		byVerdict[v] = 0
	}
	for _, r := range final {
		byVerdict[r.Verdict]++
	}

	knownTenants := []string{}
	for t := range tenantMap {
		knownTenants = append(knownTenants, t)
	}
	sort.Strings(knownTenants)
	byTenant := map[string]TenantStats{}
	for _, t := range knownTenants {
		byTenant[t] = TenantStats{TopVerdict: ""}
	}
	for _, r := range final {
		if r.Verdict == "INVALID" {
			continue
		}
		if r.TenantId == "" {
			continue
		}
		st := byTenant[r.TenantId]
		st.ChunkCount++
		if r.Verdict == "KEPT_CANONICAL" {
			st.BytesKeptCanon += r.SizeBytes
		} else if r.Verdict == "DEHYDRATED" {
			st.BytesDehydrated += r.SizeBytes
		}
		if st.TopVerdict == "" || verdictSeverity[r.Verdict] > verdictSeverity[st.TopVerdict] {
			st.TopVerdict = r.Verdict
		}
		byTenant[r.TenantId] = st
	}

	var totalKept, totalDehyd int64
	for _, r := range final {
		if r.Verdict == "KEPT_CANONICAL" {
			totalKept += r.SizeBytes
		} else if r.Verdict == "DEHYDRATED" {
			totalDehyd += r.SizeBytes
		}
	}

	digest := computeReportDigest(final, byVerdict)

	out := Output{
		ByTenant:  byTenant,
		ByVerdict: byVerdict,
		Chunks:    final,
		Summary: Summary{
			BytesDehydrated: totalDehyd,
			BytesKeptCanon:  totalKept,
			ReportDigest:    digest,
			RunTsNs:         runTsNs,
			TotalChunks:     len(final),
		},
	}

	buf, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(2)
	}
	if err := os.WriteFile("/app/output/expected.json", buf, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(2)
	}
}

func parseTierYaml(s string, mult map[string]float64, grace map[string]int64) {
	section := ""
	for _, line := range strings.Split(s, "\n") {
		raw := line
		trim := strings.TrimSpace(raw)
		if trim == "" || strings.HasPrefix(trim, "#") {
			continue
		}
		if !strings.HasPrefix(raw, " ") && !strings.HasPrefix(raw, "\t") {
			section = strings.TrimSuffix(trim, ":")
			continue
		}
		kv := strings.SplitN(trim, ":", 2)
		if len(kv) != 2 {
			continue
		}
		k := strings.TrimSpace(kv[0])
		v := strings.TrimSpace(kv[1])
		switch section {
		case "multipliers":
			if f, err := strconv.ParseFloat(v, 64); err == nil {
				mult[k] = f
			}
		case "stale_grace_ns":
			if n, err := strconv.ParseInt(v, 10, 64); err == nil {
				grace[k] = n
			}
		}
	}
}

func parseAlgorithmsToml(s string) (map[string]bool, map[string]bool) {
	strong := map[string]bool{}
	weak := map[string]bool{}
	section := ""
	for _, line := range strings.Split(s, "\n") {
		trim := strings.TrimSpace(line)
		if trim == "" || strings.HasPrefix(trim, "#") {
			continue
		}
		if strings.HasPrefix(trim, "[") && strings.HasSuffix(trim, "]") {
			section = strings.Trim(trim, "[]")
			continue
		}
		if section != "strong_set" && section != "weak_set" {
			continue
		}
		if !strings.HasPrefix(trim, "algorithms") {
			continue
		}
		idx := strings.Index(trim, "[")
		end := strings.LastIndex(trim, "]")
		if idx < 0 || end < 0 || end <= idx {
			continue
		}
		inner := trim[idx+1 : end]
		for _, item := range strings.Split(inner, ",") {
			a := strings.TrimSpace(item)
			a = strings.Trim(a, "\"'")
			if a == "" {
				continue
			}
			if section == "strong_set" {
				strong[a] = true
			} else {
				weak[a] = true
			}
		}
	}
	return strong, weak
}

func loadCanonicalBook(p string) CanonicalBook {
	var book CanonicalBook
	if err := json.Unmarshal([]byte(readFile(p)), &book); err != nil {
		fmt.Fprintf(os.Stderr, "canon book: %v\n", err)
		os.Exit(2)
	}
	return book
}

func loadTenantMap(p string) (map[string]string, map[string]string) {
	out := map[string]string{}
	tier := map[string]string{}
	for i, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" || i == 0 {
			continue
		}
		f := strings.Split(t, "|")
		if len(f) < 3 {
			continue
		}
		out[f[0]] = f[1]
		tier[f[0]] = f[2]
	}
	return out, tier
}

func loadTenantAliases(p string) map[string]string {
	out := map[string]string{}
	for _, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" || strings.HasPrefix(t, "#") {
			continue
		}
		kv := strings.SplitN(t, "=", 2)
		if len(kv) != 2 {
			continue
		}
		out[strings.TrimSpace(kv[0])] = strings.TrimSpace(kv[1])
	}
	return out
}

func loadStickyRules(p string) map[string]StickyRule {
	out := map[string]StickyRule{}
	for _, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" {
			continue
		}
		var r StickyRule
		if err := json.Unmarshal([]byte(t), &r); err == nil {
			out[r.TenantId] = r
		}
	}
	return out
}

func loadStrikes(p string) map[string]StrikeRecord {
	out := map[string]StrikeRecord{}
	for _, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" {
			continue
		}
		var r StrikeRecord
		if err := json.Unmarshal([]byte(t), &r); err == nil {
			prev, has := out[r.TenantId]
			if !has || r.LastStrikeNs > prev.LastStrikeNs {
				out[r.TenantId] = r
			}
		}
	}
	return out
}

type PriorCycleEntry struct {
	Cycle           string   `json:"cycle"`
	RunTsNs         int64    `json:"run_ts_ns"`
	AcceptedChunks  []string `json:"accepted_chunks"`
}

type CooldownEntry struct {
	TenantId         string `json:"tenant_id"`
	ReinstatedNs     int64  `json:"reinstated_ns"`
	CooldownWindowNs int64  `json:"cooldown_window_ns"`
}

func loadReplaySet(p string, runTsNs, replayWindowNs int64) map[string]bool {
	out := map[string]bool{}
	for _, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" {
			continue
		}
		var e PriorCycleEntry
		if err := json.Unmarshal([]byte(t), &e); err != nil {
			continue
		}
		if runTsNs-e.RunTsNs > replayWindowNs {
			continue
		}
		for _, cid := range e.AcceptedChunks {
			out[cid] = true
		}
	}
	return out
}

func loadCooldownSet(p string, runTsNs int64) map[string]bool {
	out := map[string]bool{}
	for _, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" {
			continue
		}
		var e CooldownEntry
		if err := json.Unmarshal([]byte(t), &e); err != nil {
			continue
		}
		if runTsNs >= e.ReinstatedNs && runTsNs <= e.ReinstatedNs+e.CooldownWindowNs {
			out[e.TenantId] = true
		}
	}
	return out
}

type BandwidthEntry struct {
	TenantId   string `json:"tenant_id"`
	Tier       string `json:"tier"`
	ByteBudget int64  `json:"byte_budget"`
}
type BandwidthTable struct {
	Budgets        []BandwidthEntry `json:"budgets"`
	DefaultBudget  int64            `json:"default_budget"`
}

func loadBandwidthBudget(p string) map[string]int64 {
	out := map[string]int64{}
	var t BandwidthTable
	if err := json.Unmarshal([]byte(readFile(p)), &t); err != nil {
		fmt.Fprintf(os.Stderr, "bandwidth table: %v\n", err)
		os.Exit(2)
	}
	for _, b := range t.Budgets {
		out[b.TenantId+"|"+b.Tier] = b.ByteBudget
	}
	return out
}

func loadRefcountHistory(p string) map[string]int64 {
	out := map[string]int64{}
	for i, line := range strings.Split(readFile(p), "\n") {
		t := strings.TrimSpace(line)
		if t == "" || i == 0 {
			continue
		}
		f := strings.Split(t, "\t")
		if len(f) < 4 {
			continue
		}
		prev, err := strconv.ParseInt(strings.TrimSpace(f[3]), 10, 64)
		if err != nil {
			continue
		}
		key := strings.TrimSpace(f[0]) + "|" + strings.TrimSpace(f[1]) + "|" + strings.TrimSpace(f[2])
		out[key] = prev
	}
	return out
}

func computeReportDigest(rows []ChunkRow, byVerdict map[string]int) string {
	var sb strings.Builder
	for _, r := range rows {
		sb.WriteString(r.ChunkId)
		sb.WriteString("|")
		sb.WriteString(r.Verdict)
		sb.WriteString("|")
		sb.WriteString(r.TenantId)
		sb.WriteString("|")
		sb.WriteString(strconv.FormatInt(r.SizeBytes, 10))
		sb.WriteString("|")
		sb.WriteString(strconv.FormatInt(r.RegisteredTsNs, 10))
		sb.WriteString("\n")
	}
	keys := []string{}
	for k := range byVerdict {
		keys = append(keys, k)
	}
	sort.Strings(keys)
	for _, k := range keys {
		sb.WriteString(k)
		sb.WriteString("=")
		sb.WriteString(strconv.Itoa(byVerdict[k]))
		sb.WriteString("\n")
	}
	sum := sha256.Sum256([]byte(sb.String()))
	return hex.EncodeToString(sum[:])[:16]
}
GOSRC

cd "${SRC_DIR}"
go build -o "${BIN_PATH}" ./...
"${BIN_PATH}"
