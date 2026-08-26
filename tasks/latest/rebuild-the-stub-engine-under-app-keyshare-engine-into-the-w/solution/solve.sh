#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/keyshare_engine /app/bin /app/output

cat > /app/keyshare_engine/main.go <<'EOF_MAIN_GO'
package main

import (
	"bufio"
	"crypto/hmac"
	"crypto/sha256"
	"encoding/csv"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

const (
	dataRoot           = "/app/data"
	serviceTiersPath   = "/app/data/service_inventory/service_tiers.yaml"
	classicGroupsPath  = "/app/data/group_catalog/classic_groups.csv"
	hybridGroupsPath   = "/app/data/group_catalog/hybrid_pq_groups.csv"
	deprecatedPath     = "/app/data/group_catalog/deprecated_groups.csv"
	bannedPath         = "/app/data/group_catalog/banned_groups.csv"
	aliasesPath        = "/app/data/group_catalog/group_aliases.csv"
	strengthPath       = "/app/data/group_catalog/security_strength.csv"
	phasesPath         = "/app/data/rollout_schedule/per_service_phases.toml"
	gracePath          = "/app/data/rollout_schedule/grace_extensions.ini"
	rateCapsPath       = "/app/data/admission_policy/rate_caps.conf"
	envelopePath       = "/app/data/admission_policy/output_envelope.json"
	monthlyAnchorPath  = "/app/data/quota_ledger/monthly_anchors.json"
	quotaCapsPath      = "/app/data/quota_ledger/quota_caps.json"
	sealPinsPath       = "/app/data/pin_seals/seal_pins.json"
	pinSecretsPath     = "/app/data/pin_seals/pin_secrets.conf"
	clientOverridePath = "/app/data/tenant_overlay/client_overrides.json"
	outputPath         = "/app/output/expected.json"
)

type Service struct {
	ID              string
	PolicyTier      string
	RateTier        string
	MinSecurityBits int
}

type Phase struct{ Start, End int64 }
type Month struct {
	Name         string
	Start, End   int64
}

type Envelope struct {
	VerdictSet               []string `json:"verdict_set"`
	VerdictSeverityHighToLow []string `json:"verdict_severity_high_to_low"`
	SuccessfulVerdicts       []string `json:"successful_verdicts"`
	DigestHexPrefixLength    int      `json:"digest_hex_prefix_length"`
	ObservationShards        []string `json:"observation_shard_paths_relative_to_data_root"`
}

type Decision struct {
	ObservationID string `json:"observation_id"`
	ServiceID     string `json:"service_id"`
	Verdict       string `json:"verdict"`
	MatchedGroup  string `json:"matched_group"`
}

type ByService struct {
	ServiceID              string `json:"service_id"`
	PreRolloutPass         int    `json:"pre_rollout_pass"`
	HybridPqOk             int    `json:"hybrid_pq_ok"`
	ClassicOk              int    `json:"classic_ok"`
	DeprecatedGrace        int    `json:"deprecated_grace"`
	SealRescued            int    `json:"seal_rescued"`
	RateLimited            int    `json:"rate_limited"`
	PolicyDowngradeBlocked int    `json:"policy_downgrade_blocked"`
	InsufficientStrength   int    `json:"insufficient_strength"`
	DuplicateObservation   int    `json:"duplicate_observation"`
	QuotaExhausted         int    `json:"quota_exhausted"`
	GroupBanned            int    `json:"group_banned"`
	RejectedType           int    `json:"rejected_type"`
	Invalid                int    `json:"invalid"`
	NoGroupsOffered        int    `json:"no_groups_offered"`
	Total                  int    `json:"total"`
}

type SealPin struct {
	ObservationID string `json:"observation_id"`
	ServiceID     string `json:"service_id"`
	ChainSeq      int    `json:"chain_seq"`
	PrevHmac      string `json:"prev_hmac"`
	Hmac8         string `json:"hmac8"`
	valid         bool
}

func read(path string) []byte {
	b, err := os.ReadFile(path)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read %s: %v\n", path, err)
		os.Exit(1)
	}
	return b
}

func parseServices() []Service {
	var out []Service
	var cur Service
	open := false
	for _, ln := range strings.Split(string(read(serviceTiersPath)), "\n") {
		t := strings.TrimSpace(ln)
		switch {
		case strings.HasPrefix(t, "- service_id:"):
			if open {
				out = append(out, cur)
			}
			cur = Service{ID: strings.TrimSpace(strings.TrimPrefix(t, "- service_id:"))}
			open = true
		case strings.HasPrefix(t, "policy_tier:"):
			cur.PolicyTier = strings.TrimSpace(strings.TrimPrefix(t, "policy_tier:"))
		case strings.HasPrefix(t, "rate_tier:"):
			cur.RateTier = strings.TrimSpace(strings.TrimPrefix(t, "rate_tier:"))
		case strings.HasPrefix(t, "min_security_bits:"):
			v := strings.TrimSpace(strings.TrimPrefix(t, "min_security_bits:"))
			cur.MinSecurityBits, _ = strconv.Atoi(v)
		}
	}
	if open {
		out = append(out, cur)
	}
	return out
}

func loadGroupSet(path string) map[string]bool {
	r := csv.NewReader(strings.NewReader(string(read(path))))
	rows, err := r.ReadAll()
	if err != nil {
		fmt.Fprintf(os.Stderr, "csv %s: %v\n", path, err)
		os.Exit(1)
	}
	s := map[string]bool{}
	for i, row := range rows {
		if i == 0 || len(row) == 0 {
			continue
		}
		s[strings.ToLower(strings.TrimSpace(row[0]))] = true
	}
	return s
}

func loadAliases() map[string]string {
	r := csv.NewReader(strings.NewReader(string(read(aliasesPath))))
	rows, err := r.ReadAll()
	if err != nil {
		fmt.Fprintf(os.Stderr, "csv %s: %v\n", aliasesPath, err)
		os.Exit(1)
	}
	out := map[string]string{}
	for i, row := range rows {
		if i == 0 || len(row) < 2 {
			continue
		}
		out[strings.ToLower(strings.TrimSpace(row[0]))] = strings.ToLower(strings.TrimSpace(row[1]))
	}
	return out
}

func loadStrength() map[string]int {
	r := csv.NewReader(strings.NewReader(string(read(strengthPath))))
	rows, err := r.ReadAll()
	if err != nil {
		fmt.Fprintf(os.Stderr, "csv %s: %v\n", strengthPath, err)
		os.Exit(1)
	}
	out := map[string]int{}
	for i, row := range rows {
		if i == 0 || len(row) < 2 {
			continue
		}
		bits, _ := strconv.Atoi(strings.TrimSpace(row[1]))
		out[strings.ToLower(strings.TrimSpace(row[0]))] = bits
	}
	return out
}

func parsePhases() map[string]Phase {
	out := map[string]Phase{}
	var key string
	cur := Phase{}
	flush := func() {
		if key != "" {
			out[key] = cur
		}
	}
	for _, ln := range strings.Split(string(read(phasesPath)), "\n") {
		t := strings.TrimSpace(ln)
		if strings.HasPrefix(t, "[") && strings.HasSuffix(t, "]") {
			flush()
			key = t[1 : len(t)-1]
			cur = Phase{}
			continue
		}
		if strings.HasPrefix(t, "rollout_start_ns") {
			v := strings.TrimSpace(strings.SplitN(t, "=", 2)[1])
			cur.Start, _ = strconv.ParseInt(v, 10, 64)
		} else if strings.HasPrefix(t, "rollout_end_ns") {
			v := strings.TrimSpace(strings.SplitN(t, "=", 2)[1])
			cur.End, _ = strconv.ParseInt(v, 10, 64)
		}
	}
	flush()
	return out
}

func parseGrace() map[string]int64 {
	out := map[string]int64{}
	var key string
	for _, ln := range strings.Split(string(read(gracePath)), "\n") {
		t := strings.TrimSpace(ln)
		if strings.HasPrefix(t, "[") && strings.HasSuffix(t, "]") {
			key = t[1 : len(t)-1]
			continue
		}
		if strings.HasPrefix(t, "grace_extension_ns") {
			v := strings.TrimSpace(strings.SplitN(t, "=", 2)[1])
			n, _ := strconv.ParseInt(v, 10, 64)
			out[key] = n
		}
	}
	return out
}

func parseRate() (int64, int, map[string]int) {
	var window int64
	base := 0
	mult := map[string]int{}
	for _, ln := range strings.Split(string(read(rateCapsPath)), "\n") {
		t := strings.TrimSpace(ln)
		if t == "" {
			continue
		}
		parts := strings.SplitN(t, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.TrimSpace(parts[1])
		switch {
		case k == "window_ns":
			window, _ = strconv.ParseInt(v, 10, 64)
		case k == "base_cap":
			base, _ = strconv.Atoi(v)
		case strings.HasSuffix(k, "_multiplier"):
			tier := strings.TrimSuffix(k, "_multiplier")
			n, _ := strconv.Atoi(v)
			mult[tier] = n
		}
	}
	return window, base, mult
}

func loadEnvelope() Envelope {
	var e Envelope
	if err := json.Unmarshal(read(envelopePath), &e); err != nil {
		fmt.Fprintf(os.Stderr, "envelope: %v\n", err)
		os.Exit(1)
	}
	return e
}

func loadMonths() []Month {
	var doc struct {
		Months []struct {
			Name    string `json:"name"`
			StartNs int64  `json:"start_ns"`
			EndNs   int64  `json:"end_ns"`
		} `json:"months"`
	}
	if err := json.Unmarshal(read(monthlyAnchorPath), &doc); err != nil {
		fmt.Fprintf(os.Stderr, "months: %v\n", err)
		os.Exit(1)
	}
	out := make([]Month, len(doc.Months))
	for i, m := range doc.Months {
		out[i] = Month{Name: m.Name, Start: m.StartNs, End: m.EndNs}
	}
	return out
}

func loadQuotaCaps() map[string]map[string]int {
	var doc struct {
		Caps []struct {
			ServiceID string `json:"service_id"`
			Month     string `json:"month"`
			AdmitCap  int    `json:"admit_cap"`
		} `json:"caps"`
	}
	if err := json.Unmarshal(read(quotaCapsPath), &doc); err != nil {
		fmt.Fprintf(os.Stderr, "quota: %v\n", err)
		os.Exit(1)
	}
	out := map[string]map[string]int{}
	for _, c := range doc.Caps {
		if _, ok := out[c.ServiceID]; !ok {
			out[c.ServiceID] = map[string]int{}
		}
		out[c.ServiceID][c.Month] = c.AdmitCap
	}
	return out
}

func loadSealPins() map[string]*SealPin {
	var doc struct {
		Pins []SealPin `json:"pins"`
	}
	if err := json.Unmarshal(read(sealPinsPath), &doc); err != nil {
		fmt.Fprintf(os.Stderr, "pins: %v\n", err)
		os.Exit(1)
	}
	// Group pins by service, sort by chain_seq, validate chain.
	perService := map[string][]*SealPin{}
	for i := range doc.Pins {
		p := &doc.Pins[i]
		p.Hmac8 = strings.ToLower(strings.TrimSpace(p.Hmac8))
		p.PrevHmac = strings.ToLower(strings.TrimSpace(p.PrevHmac))
		perService[p.ServiceID] = append(perService[p.ServiceID], p)
	}
	for _, pins := range perService {
		sort.Slice(pins, func(i, j int) bool { return pins[i].ChainSeq < pins[j].ChainSeq })
		chainOK := true
		prev := ""
		for _, p := range pins {
			if !chainOK {
				p.valid = false
				continue
			}
			if p.ChainSeq == 1 {
				if p.PrevHmac != "" {
					chainOK = false
					p.valid = false
					continue
				}
			} else {
				if p.PrevHmac != prev {
					chainOK = false
					p.valid = false
					continue
				}
			}
			p.valid = true
			prev = p.Hmac8
		}
	}
	// Index by observation_id for O(1) lookup.
	out := map[string]*SealPin{}
	for _, p := range doc.Pins {
		pp := p
		out[p.ObservationID] = &pp
	}
	// Overwrite with valid-flagged pointers from perService slices.
	for _, pins := range perService {
		for _, p := range pins {
			out[p.ObservationID] = p
		}
	}
	return out
}

type PinSecrets struct {
	Key       string
	Algorithm string
	PrefixLen int
}

func loadPinSecrets() PinSecrets {
	ps := PinSecrets{Algorithm: "sha256", PrefixLen: 16}
	for _, ln := range strings.Split(string(read(pinSecretsPath)), "\n") {
		t := strings.TrimSpace(ln)
		if t == "" {
			continue
		}
		parts := strings.SplitN(t, "=", 2)
		if len(parts) != 2 {
			continue
		}
		k := strings.TrimSpace(parts[0])
		v := strings.TrimSpace(parts[1])
		switch k {
		case "hmac_key":
			ps.Key = v
		case "hmac_algorithm":
			ps.Algorithm = v
		case "hmac_hex_prefix_length":
			ps.PrefixLen, _ = strconv.Atoi(v)
		}
	}
	return ps
}

func loadClientOverrides() map[string]string {
	var doc struct {
		Overrides []struct {
			ClientID           string `json:"client_id"`
			OverridePolicyTier string `json:"override_policy_tier"`
		} `json:"overrides"`
	}
	if err := json.Unmarshal(read(clientOverridePath), &doc); err != nil {
		fmt.Fprintf(os.Stderr, "overrides: %v\n", err)
		os.Exit(1)
	}
	out := map[string]string{}
	for _, o := range doc.Overrides {
		out[o.ClientID] = o.OverridePolicyTier
	}
	return out
}

func computeHmac8(key, preimage string, prefixLen int) string {
	h := hmac.New(sha256.New, []byte(key))
	h.Write([]byte(preimage))
	return hex.EncodeToString(h.Sum(nil))[:prefixLen]
}

type RawObs struct {
	Raw     map[string]json.RawMessage
	ShardID int
	Index   int
}

func loadAllObservations(envelope Envelope) []RawObs {
	var obs []RawObs
	for shardIdx, rel := range envelope.ObservationShards {
		path := filepath.Join(dataRoot, rel)
		fp, err := os.Open(path)
		if err != nil {
			fmt.Fprintf(os.Stderr, "open %s: %v\n", path, err)
			os.Exit(1)
		}
		sc := bufio.NewScanner(fp)
		sc.Buffer(make([]byte, 1024*1024), 1024*1024)
		i := 0
		for sc.Scan() {
			line := strings.TrimSpace(sc.Text())
			if line == "" {
				continue
			}
			var raw map[string]json.RawMessage
			if err := json.Unmarshal([]byte(line), &raw); err != nil {
				obs = append(obs, RawObs{Raw: nil, ShardID: shardIdx, Index: i})
				i++
				continue
			}
			obs = append(obs, RawObs{Raw: raw, ShardID: shardIdx, Index: i})
			i++
		}
		fp.Close()
	}
	return obs
}

func monthOf(ts int64, months []Month) string {
	for _, m := range months {
		if ts >= m.Start && ts < m.End {
			return m.Name
		}
	}
	return ""
}

func main() {
	services := parseServices()
	svcByID := map[string]Service{}
	for _, s := range services {
		svcByID[s.ID] = s
	}
	classics := loadGroupSet(classicGroupsPath)
	hybrids := loadGroupSet(hybridGroupsPath)
	deprecated := loadGroupSet(deprecatedPath)
	banned := loadGroupSet(bannedPath)
	aliases := loadAliases()
	strength := loadStrength()
	phases := parsePhases()
	grace := parseGrace()
	window, base, mult := parseRate()
	envelope := loadEnvelope()
	months := loadMonths()
	quotaCaps := loadQuotaCaps()
	sealPins := loadSealPins()
	secrets := loadPinSecrets()
	clientOverrides := loadClientOverrides()

	severity := map[string]int{}
	for i, v := range envelope.VerdictSeverityHighToLow {
		severity[v] = i
	}
	successful := map[string]bool{}
	for _, v := range envelope.SuccessfulVerdicts {
		successful[v] = true
	}

	rawObs := loadAllObservations(envelope)

	type Parsed struct {
		Idx            int
		ObsID          string
		SvcID          string
		ClientID       string
		Ts             int64
		Offered        []string
		TsPresent      bool
		OfferedPresent bool
		RejType        bool
		Decision       Decision
		Done           bool
	}
	parsed := make([]Parsed, 0, len(rawObs))
	for idx, ro := range rawObs {
		p := Parsed{Idx: idx}
		if ro.Raw == nil {
			p.Decision = Decision{Verdict: "INVALID"}
			p.Done = true
			parsed = append(parsed, p)
			continue
		}
		raw := ro.Raw
		if v, ok := raw["observation_id"]; ok {
			if json.Unmarshal(v, &p.ObsID) != nil {
				p.RejType = true
			}
		}
		if v, ok := raw["service_id"]; ok {
			if json.Unmarshal(v, &p.SvcID) != nil {
				p.RejType = true
			}
		}
		if v, ok := raw["observed_ts_ns"]; ok {
			p.TsPresent = true
			if json.Unmarshal(v, &p.Ts) != nil {
				p.RejType = true
			}
		}
		if v, ok := raw["offered_groups"]; ok {
			p.OfferedPresent = true
			if json.Unmarshal(v, &p.Offered) != nil {
				p.RejType = true
			}
			for i, g := range p.Offered {
				p.Offered[i] = strings.ToLower(strings.TrimSpace(g))
			}
		}
		if v, ok := raw["client_id"]; ok {
			if json.Unmarshal(v, &p.ClientID) != nil {
				p.RejType = true
			}
		}
		p.Decision.ObservationID = p.ObsID
		p.Decision.ServiceID = p.SvcID
		parsed = append(parsed, p)
	}

	// GLOBAL sort by (observed_ts_ns asc, observation_id asc) for processing.
	sort.SliceStable(parsed, func(i, j int) bool {
		if parsed[i].Ts != parsed[j].Ts {
			return parsed[i].Ts < parsed[j].Ts
		}
		return parsed[i].ObsID < parsed[j].ObsID
	})

	rateHistory := map[string][]int64{}
	quotaCount := map[string]map[string]int{}
	seenObsIDs := map[string]bool{}

	resolve := func(g string) string {
		if c, ok := aliases[g]; ok {
			return c
		}
		return g
	}

	for i := range parsed {
		p := &parsed[i]
		if p.Done {
			continue
		}
		d := &p.Decision

		// Gate 1: type-strict
		if p.RejType {
			d.Verdict = "REJECTED_TYPE"
			continue
		}
		// Gate 2: required
		if p.ObsID == "" || p.SvcID == "" || !p.TsPresent || !p.OfferedPresent {
			d.Verdict = "INVALID"
			continue
		}
		// Gate 3: empty offered_groups
		if len(p.Offered) == 0 {
			d.Verdict = "NO_GROUPS_OFFERED"
			continue
		}
		// Gate 4: service lookup
		svc, found := svcByID[p.SvcID]
		if !found {
			d.Verdict = "UNKNOWN_SERVICE"
			continue
		}
		// Gate 5: banned (with chain-verified seal rescue)
		bannedHit := ""
		for _, g := range p.Offered {
			canon := resolve(g)
			if banned[g] || banned[canon] {
				bannedHit = g
				break
			}
		}
		if bannedHit != "" {
			pin, hasPin := sealPins[p.ObsID]
			if hasPin && pin.valid {
				expected := computeHmac8(secrets.Key,
					p.ObsID+"|"+p.SvcID+"|"+p.ClientID, secrets.PrefixLen)
				if hmac.Equal([]byte(pin.Hmac8), []byte(expected)) {
					d.Verdict = "SEAL_RESCUED"
					d.MatchedGroup = bannedHit
					continue
				}
			}
			d.Verdict = "GROUP_BANNED"
			d.MatchedGroup = bannedHit
			continue
		}
		// Gate 6: dedup by observation_id (BEFORE quota so a duplicate does not consume a slot)
		if seenObsIDs[p.ObsID] {
			d.Verdict = "DUPLICATE_OBSERVATION"
			continue
		}
		seenObsIDs[p.ObsID] = true
		// Gate 7: quota
		monthName := monthOf(p.Ts, months)
		capQuota := 0
		if monthName != "" {
			if svcCaps, ok := quotaCaps[p.SvcID]; ok {
				capQuota = svcCaps[monthName]
			}
		}
		if quotaCount[p.SvcID] == nil {
			quotaCount[p.SvcID] = map[string]int{}
		}
		if monthName != "" && capQuota > 0 {
			cur := quotaCount[p.SvcID][monthName]
			if cur >= capQuota {
				d.Verdict = "QUOTA_EXHAUSTED"
				continue
			}
			quotaCount[p.SvcID][monthName] = cur + 1
		}
		// Gate 8: rate limit
		capRate := base * mult[svc.RateTier]
		cutoff := p.Ts - window
		hist := rateHistory[p.SvcID]
		count := 0
		for _, h := range hist {
			if h >= cutoff {
				count++
			}
		}
		if count >= capRate {
			d.Verdict = "RATE_LIMITED"
			continue
		}
		rateHistory[p.SvcID] = append(hist, p.Ts)

		// Gate 9: phase resolution + strength
		effectiveTier := svc.PolicyTier
		if ov, ok := clientOverrides[p.ClientID]; ok {
			effectiveTier = ov
		}
		ph := phases[p.SvcID]
		graceExt := grace[svc.RateTier]
		graceEnd := ph.End + graceExt
		var phase string
		switch {
		case p.Ts < ph.Start:
			phase = "pre"
		case p.Ts < ph.End:
			phase = "rollout"
		case p.Ts < graceEnd:
			phase = "grace"
		default:
			phase = "post"
		}

		if phase == "pre" {
			d.Verdict = "PRE_ROLLOUT_PASS"
			continue
		}

		// Classify offered groups (with alias resolution).
		var hybridHit, classicHit, deprecatedHit string
		maxOfferedBits := -1
		for _, g := range p.Offered {
			canon := resolve(g)
			if hybridHit == "" && hybrids[canon] {
				hybridHit = canon
			}
			if classicHit == "" && classics[canon] {
				classicHit = canon
			}
			if deprecatedHit == "" && deprecated[canon] {
				deprecatedHit = canon
			}
			if bits, ok := strength[canon]; ok && bits > maxOfferedBits {
				maxOfferedBits = bits
			}
		}
		// Strength gate (only past rollout_start).
		if maxOfferedBits >= 0 && svc.MinSecurityBits > 0 && maxOfferedBits < svc.MinSecurityBits {
			d.Verdict = "INSUFFICIENT_STRENGTH"
			continue
		}

		// Phase-tier verdict.
		switch phase {
		case "rollout":
			switch {
			case hybridHit != "":
				d.Verdict = "HYBRID_PQ_OK"
				d.MatchedGroup = hybridHit
			case classicHit != "":
				d.Verdict = "CLASSIC_OK"
				d.MatchedGroup = classicHit
			case deprecatedHit != "":
				d.Verdict = "DEPRECATED_GRACE"
				d.MatchedGroup = deprecatedHit
			default:
				d.Verdict = "POLICY_DOWNGRADE_BLOCKED"
			}
		case "grace":
			switch {
			case hybridHit != "":
				d.Verdict = "HYBRID_PQ_OK"
				d.MatchedGroup = hybridHit
			case effectiveTier == "pq_mandatory":
				d.Verdict = "POLICY_DOWNGRADE_BLOCKED"
			case classicHit != "":
				d.Verdict = "CLASSIC_OK"
				d.MatchedGroup = classicHit
			case deprecatedHit != "":
				d.Verdict = "DEPRECATED_GRACE"
				d.MatchedGroup = deprecatedHit
			default:
				d.Verdict = "POLICY_DOWNGRADE_BLOCKED"
			}
		case "post":
			switch {
			case hybridHit != "":
				d.Verdict = "HYBRID_PQ_OK"
				d.MatchedGroup = hybridHit
			case effectiveTier == "pq_mandatory":
				d.Verdict = "POLICY_DOWNGRADE_BLOCKED"
			case classicHit != "":
				d.Verdict = "CLASSIC_OK"
				d.MatchedGroup = classicHit
			default:
				d.Verdict = "POLICY_DOWNGRADE_BLOCKED"
			}
		}
	}

	decisions := make([]Decision, 0, len(parsed))
	for _, p := range parsed {
		decisions = append(decisions, p.Decision)
	}

	byVerdict := map[string]int{}
	for _, v := range envelope.VerdictSet {
		byVerdict[v] = 0
	}
	for _, d := range decisions {
		byVerdict[d.Verdict]++
	}

	bsm := map[string]*ByService{}
	for _, s := range services {
		bsm[s.ID] = &ByService{ServiceID: s.ID}
	}
	for _, d := range decisions {
		if d.ServiceID == "" {
			continue
		}
		bs, ok := bsm[d.ServiceID]
		if !ok {
			continue
		}
		bs.Total++
		switch d.Verdict {
		case "PRE_ROLLOUT_PASS":
			bs.PreRolloutPass++
		case "HYBRID_PQ_OK":
			bs.HybridPqOk++
		case "CLASSIC_OK":
			bs.ClassicOk++
		case "DEPRECATED_GRACE":
			bs.DeprecatedGrace++
		case "SEAL_RESCUED":
			bs.SealRescued++
		case "RATE_LIMITED":
			bs.RateLimited++
		case "POLICY_DOWNGRADE_BLOCKED":
			bs.PolicyDowngradeBlocked++
		case "INSUFFICIENT_STRENGTH":
			bs.InsufficientStrength++
		case "DUPLICATE_OBSERVATION":
			bs.DuplicateObservation++
		case "QUOTA_EXHAUSTED":
			bs.QuotaExhausted++
		case "GROUP_BANNED":
			bs.GroupBanned++
		case "REJECTED_TYPE":
			bs.RejectedType++
		case "INVALID":
			bs.Invalid++
		case "NO_GROUPS_OFFERED":
			bs.NoGroupsOffered++
		}
	}
	var svcIDs []string
	for id := range bsm {
		svcIDs = append(svcIDs, id)
	}
	sort.Strings(svcIDs)
	var bsList []*ByService
	for _, id := range svcIDs {
		bsList = append(bsList, bsm[id])
	}

	tsByObs := map[string]int64{}
	for _, p := range parsed {
		if _, ok := tsByObs[p.ObsID]; !ok {
			tsByObs[p.ObsID] = p.Ts
		}
	}
	// Sort decisions for output: severity desc, service_id asc, observed_ts_ns asc (of the row), observation_id asc.
	// Since duplicates share obs_id we tie-break by original ts of each parsed entry using its idx position.
	posByPtr := map[*Decision]int{}
	for i := range parsed {
		posByPtr[&decisions[i]] = i
	}
	sort.SliceStable(decisions, func(i, j int) bool {
		si, sj := severity[decisions[i].Verdict], severity[decisions[j].Verdict]
		if si != sj {
			return si < sj
		}
		if decisions[i].ServiceID != decisions[j].ServiceID {
			return decisions[i].ServiceID < decisions[j].ServiceID
		}
		ti := parsed[posByPtr[&decisions[i]]].Ts
		tj := parsed[posByPtr[&decisions[j]]].Ts
		if ti != tj {
			return ti < tj
		}
		return decisions[i].ObservationID < decisions[j].ObservationID
	})

	total := len(decisions)
	succ := 0
	for _, d := range decisions {
		if successful[d.Verdict] {
			succ++
		}
	}
	rejected := total - succ

	var pre []string
	for _, d := range decisions {
		pre = append(pre, fmt.Sprintf("D|%s|%s|%s|%s",
			d.ObservationID, d.ServiceID, d.Verdict, d.MatchedGroup))
	}
	for _, bs := range bsList {
		pre = append(pre, fmt.Sprintf("S|%s|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d|%d",
			bs.ServiceID, bs.PreRolloutPass, bs.HybridPqOk, bs.ClassicOk,
			bs.DeprecatedGrace, bs.SealRescued, bs.RateLimited,
			bs.PolicyDowngradeBlocked, bs.InsufficientStrength,
			bs.DuplicateObservation, bs.QuotaExhausted, bs.GroupBanned,
			bs.RejectedType, bs.Invalid, bs.NoGroupsOffered, bs.Total))
	}
	pre = append(pre, fmt.Sprintf("T|%d|%d|%d", total, succ, rejected))
	h := sha256.Sum256([]byte(strings.Join(pre, "\n")))
	digest := hex.EncodeToString(h[:])[:envelope.DigestHexPrefixLength]

	out := map[string]any{
		"decisions":  decisions,
		"by_service": bsList,
		"by_verdict": byVerdict,
		"summary": map[string]any{
			"total_observations": total,
			"successful":         succ,
			"rejected":           rejected,
			"report_digest":      digest,
		},
	}

	if err := os.MkdirAll("/app/output", 0o755); err != nil {
		os.Exit(1)
	}
	fout, err := os.Create(outputPath)
	if err != nil {
		os.Exit(1)
	}
	defer fout.Close()
	enc := json.NewEncoder(fout)
	enc.SetIndent("", "  ")
	if err := enc.Encode(out); err != nil {
		os.Exit(1)
	}
}
EOF_MAIN_GO

cat > /app/keyshare_engine/go.mod <<'EOF_GO_MOD'
module keyshare_witness

go 1.24
EOF_GO_MOD

cd /app/keyshare_engine
go build -o /app/bin/keyshare_witness .

/app/bin/keyshare_witness
