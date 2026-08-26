package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"net/netip"
	"os"
	"sort"
	"strconv"
	"strings"
)

type Key struct {
	ID        string `json:"id"`
	Secret    string `json:"secret"`
	NotBefore int64  `json:"not_before"`
	NotAfter  int64  `json:"not_after"`
}

type DischargeKey struct {
	Location  string `json:"location"`
	KeyID     string `json:"key_id"`
	Secret    string `json:"secret"`
	NotBefore int64  `json:"not_before"`
	NotAfter  int64  `json:"not_after"`
}

type Caveat struct {
	Type        string          `json:"type"`
	Value       json.RawMessage `json:"value,omitempty"`
	CaveatID    string          `json:"caveat_id,omitempty"`
	Location    string          `json:"location,omitempty"`
	KeyID       string          `json:"key_id,omitempty"`
	Threshold   int             `json:"threshold,omitempty"`
	Authorities []Authority     `json:"authorities,omitempty"`
}

type Authority struct {
	Location string `json:"location"`
	KeyID    string `json:"key_id"`
}

type Primary struct {
	Identifier string   `json:"identifier"`
	Location   string   `json:"location"`
	RootKeyID  string   `json:"root_key_id"`
	Caveats    []Caveat `json:"caveats"`
	Signature  string   `json:"signature"`
}

type Discharge struct {
	InstanceID string   `json:"instance_id"`
	ReplayID   string   `json:"replay_id"`
	Identifier string   `json:"identifier"`
	Location   string   `json:"location"`
	KeyID      string   `json:"key_id"`
	Caveats    []Caveat `json:"caveats"`
	Signature  string   `json:"signature"`
	Binding    string   `json:"binding"`
	Attachment string   `json:"attachment"`
}

type NonceRef struct {
	Identifier string `json:"identifier"`
	Nonce      string `json:"nonce"`
}

type DischargeRef struct {
	Location string `json:"location"`
	KeyID    string `json:"key_id"`
	ReplayID string `json:"replay_id"`
}

type Request struct {
	ID         string      `json:"id"`
	Timestamp  int64       `json:"timestamp"`
	Method     string      `json:"method"`
	Path       string      `json:"path"`
	IP         string      `json:"ip"`
	Scopes     []string    `json:"scopes"`
	Body       string      `json:"body"`
	Nonce      string      `json:"nonce"`
	Macaroon   Primary     `json:"macaroon"`
	Discharges []Discharge `json:"discharges"`
}

type Input struct {
	EvaluationTime     int64          `json:"evaluation_time"`
	MaxSkewSeconds     int64          `json:"max_skew_seconds"`
	RootKeys           []Key          `json:"root_keys"`
	DischargeKeys      []DischargeKey `json:"discharge_keys"`
	RevokedIdentifiers []string       `json:"revoked_identifiers"`
	ReservedNonces     []NonceRef     `json:"reserved_nonces"`
	SpentDischarges    []DischargeRef `json:"spent_discharges"`
	Requests           []Request      `json:"requests"`
}

type Normalized struct {
	Method     string   `json:"method"`
	Path       string   `json:"path"`
	IP         string   `json:"ip"`
	Scopes     []string `json:"scopes"`
	BodySHA256 string   `json:"body_sha256"`
}

type DischargeResult struct {
	InstanceID string   `json:"instance_id"`
	Usable     bool     `json:"usable"`
	Reasons    []string `json:"reasons"`
}

type Decision struct {
	ID               string            `json:"id"`
	Decision         string            `json:"decision"`
	Reasons          []string          `json:"reasons"`
	Normalized       Normalized        `json:"normalized"`
	PrimaryCaveats   []string          `json:"primary_caveats"`
	UsedDischarges   []string          `json:"used_discharges"`
	DischargeResults []DischargeResult `json:"discharge_results"`
}

type Summary struct {
	Allowed      int            `json:"allowed"`
	Denied       int            `json:"denied"`
	ReasonCounts map[string]int `json:"reason_counts"`
}

type Report struct {
	EvaluatedAt int64      `json:"evaluated_at"`
	Decisions   []Decision `json:"decisions"`
	Summary     Summary    `json:"summary"`
	FinalState  FinalState `json:"final_state"`
}

type FinalState struct {
	ReservedNonces  []NonceRef     `json:"reserved_nonces"`
	SpentDischarges []DischargeRef `json:"spent_discharges"`
}

var primaryOrder = []string{
	"unknown_root_key", "root_key_inactive", "revoked_identifier", "bad_primary_signature",
	"timestamp_skew", "replayed_nonce", "first_party_unsatisfied", "third_party_unsatisfied", "unused_discharge",
}

var dischargeOrder = []string{
	"unknown_discharge_key", "discharge_key_inactive", "revoked_identifier",
	"replayed_discharge", "bad_discharge_signature", "bad_binding", "first_party_unsatisfied",
}

func normalizePath(value string) string {
	parts := []string{}
	for _, part := range strings.Split(value, "/") {
		switch part {
		case "", ".":
			continue
		case "..":
			if len(parts) > 0 {
				parts = parts[:len(parts)-1]
			}
		default:
			parts = append(parts, part)
		}
	}
	return "/" + strings.Join(parts, "/")
}

func stringValue(c Caveat) string {
	var value string
	_ = json.Unmarshal(c.Value, &value)
	return value
}

func intValue(c Caveat) int64 {
	var value int64
	_ = json.Unmarshal(c.Value, &value)
	return value
}

func canonicalCaveat(c Caveat) string {
	switch c.Type {
	case "time_before", "time_after":
		return c.Type + "|" + strconv.FormatInt(intValue(c), 10)
	case "method":
		return "method|" + strings.ToUpper(stringValue(c))
	case "path_prefix":
		return "path_prefix|" + normalizePath(stringValue(c))
	case "ip_cidr":
		prefix, _ := netip.ParsePrefix(stringValue(c))
		return "ip_cidr|" + prefix.Masked().String()
	case "scope":
		return "scope|" + stringValue(c)
	case "body_sha256":
		return "body_sha256|" + strings.ToLower(stringValue(c))
	case "third_party":
		return "third_party|" + c.CaveatID + "|" + c.Location + "|" + c.KeyID
	case "third_party_quorum":
		var builder strings.Builder
		builder.WriteString("third_party_quorum|")
		builder.WriteString(c.CaveatID)
		builder.WriteByte('|')
		builder.WriteString(strconv.Itoa(c.Threshold))
		for _, authority := range c.Authorities {
			builder.WriteByte('|')
			builder.WriteString(authority.Location)
			builder.WriteByte('|')
			builder.WriteString(authority.KeyID)
		}
		return builder.String()
	}
	return ""
}

func hmacBytes(key, message []byte) []byte {
	m := hmac.New(sha256.New, key)
	_, _ = m.Write(message)
	return m.Sum(nil)
}

func primarySignature(secret string, token Primary) string {
	current := hmacBytes([]byte(secret), []byte("M1\n"+token.Location+"\n"+token.Identifier+"\n"+token.RootKeyID))
	for _, caveat := range token.Caveats {
		current = hmacBytes(current, []byte(canonicalCaveat(caveat)))
	}
	return hex.EncodeToString(current)
}

func dischargeSignature(secret string, token Discharge) string {
	current := hmacBytes([]byte(secret), []byte("D1\n"+token.Location+"\n"+token.Identifier+"\n"+token.KeyID+"\n"+token.ReplayID))
	for _, caveat := range token.Caveats {
		current = hmacBytes(current, []byte(canonicalCaveat(caveat)))
	}
	return hex.EncodeToString(current)
}

func strictHex(value string) ([]byte, bool) {
	if len(value) != 64 {
		return nil, false
	}
	for _, ch := range value {
		if !((ch >= '0' && ch <= '9') || (ch >= 'a' && ch <= 'f')) {
			return nil, false
		}
	}
	decoded, err := hex.DecodeString(value)
	return decoded, err == nil && len(decoded) == 32
}

func secureHexEqual(supplied, expected string) bool {
	if _, ok := strictHex(supplied); !ok {
		return false
	}
	return hmac.Equal([]byte(supplied), []byte(expected))
}

func bindingMatches(primarySig, dischargeSig, binding string) bool {
	p, okP := strictHex(primarySig)
	d, okD := strictHex(dischargeSig)
	if !okP || !okD {
		return false
	}
	expected := hex.EncodeToString(hmacBytes(p, d))
	return secureHexEqual(binding, expected)
}

func attachmentMatches(parentSig string, caveat Caveat, dischargeSig, attachment string) bool {
	p, okP := strictHex(parentSig)
	d, okD := strictHex(dischargeSig)
	if !okP || !okD {
		return false
	}
	message := append([]byte(canonicalCaveat(caveat)), 0)
	message = append(message, d...)
	expected := hex.EncodeToString(hmacBytes(p, message))
	return secureHexEqual(attachment, expected)
}

func normalizeRequest(req Request) Normalized {
	addr, _ := netip.ParseAddr(req.IP)
	scopes := append([]string{}, req.Scopes...)
	sort.Strings(scopes)
	digest := sha256.Sum256([]byte(req.Body))
	return Normalized{
		Method: strings.ToUpper(req.Method), Path: normalizePath(req.Path), IP: addr.String(),
		Scopes: scopes, BodySHA256: hex.EncodeToString(digest[:]),
	}
}

func scopeCovers(caveatScope, requested string) bool {
	if caveatScope == "*" {
		return true
	}
	if strings.HasSuffix(caveatScope, ":*") {
		return strings.HasPrefix(requested, caveatScope[:len(caveatScope)-1])
	}
	return caveatScope == requested
}

func firstPartyOK(caveats []Caveat, req Request, norm Normalized) bool {
	for _, caveat := range caveats {
		switch caveat.Type {
		case "third_party", "third_party_quorum":
			continue
		case "time_before":
			if !(req.Timestamp < intValue(caveat)) {
				return false
			}
		case "time_after":
			if !(req.Timestamp >= intValue(caveat)) {
				return false
			}
		case "method":
			if norm.Method != strings.ToUpper(stringValue(caveat)) {
				return false
			}
		case "path_prefix":
			prefix := normalizePath(stringValue(caveat))
			if prefix != "/" && norm.Path != prefix && !strings.HasPrefix(norm.Path, prefix+"/") {
				return false
			}
		case "ip_cidr":
			prefix, _ := netip.ParsePrefix(stringValue(caveat))
			addr, _ := netip.ParseAddr(norm.IP)
			if !prefix.Contains(addr) {
				return false
			}
		case "scope":
			for _, requested := range req.Scopes {
				if !scopeCovers(stringValue(caveat), requested) {
					return false
				}
			}
		case "body_sha256":
			if norm.BodySHA256 != strings.ToLower(stringValue(caveat)) {
				return false
			}
		}
	}
	return true
}

func contains(values map[string]bool, key string) bool { return values[key] }

func orderedReasons(found map[string]bool, order []string) []string {
	result := []string{}
	for _, reason := range order {
		if found[reason] {
			result = append(result, reason)
		}
	}
	return result
}

func dischargeReplayKey(location, keyID, replayID string) string {
	return location + "\x00" + keyID + "\x00" + replayID
}

func auditDischarges(input Input, req Request, norm Normalized, revoked, spent map[string]bool) ([]DischargeResult, []bool) {
	keys := map[string]DischargeKey{}
	for _, key := range input.DischargeKeys {
		keys[key.Location+"\x00"+key.KeyID] = key
	}
	results := make([]DischargeResult, 0, len(req.Discharges))
	usable := make([]bool, len(req.Discharges))
	for i, token := range req.Discharges {
		found := map[string]bool{}
		key, known := keys[token.Location+"\x00"+token.KeyID]
		if !known {
			found["unknown_discharge_key"] = true
		} else {
			if req.Timestamp < key.NotBefore || req.Timestamp > key.NotAfter {
				found["discharge_key_inactive"] = true
			}
			if !secureHexEqual(token.Signature, dischargeSignature(key.Secret, token)) {
				found["bad_discharge_signature"] = true
			}
		}
		if revoked[token.Identifier] {
			found["revoked_identifier"] = true
		}
		if spent[dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)] {
			found["replayed_discharge"] = true
		}
		if !bindingMatches(req.Macaroon.Signature, token.Signature, token.Binding) {
			found["bad_binding"] = true
		}
		if !firstPartyOK(token.Caveats, req, norm) {
			found["first_party_unsatisfied"] = true
		}
		reasons := orderedReasons(found, dischargeOrder)
		usable[i] = len(reasons) == 0
		results = append(results, DischargeResult{InstanceID: token.InstanceID, Usable: usable[i], Reasons: reasons})
	}
	return results, usable
}

func thirdCaveats(caveats []Caveat) []Caveat {
	result := []Caveat{}
	for _, caveat := range caveats {
		if caveat.Type == "third_party" || caveat.Type == "third_party_quorum" {
			result = append(result, caveat)
		}
	}
	return result
}

type proofTask struct {
	Caveat          Caveat
	ParentSignature string
}

type assignment struct {
	InstanceIDs []string
	Indexes     []int
}

func proofTasks(caveats []Caveat, parentSignature string) []proofTask {
	tasks := []proofTask{}
	for _, caveat := range caveats {
		if caveat.Type == "third_party" || caveat.Type == "third_party_quorum" {
			tasks = append(tasks, proofTask{Caveat: caveat, ParentSignature: parentSignature})
		}
	}
	return tasks
}

func authorityAllowed(caveat Caveat, token Discharge) bool {
	for _, authority := range caveat.Authorities {
		if authority.Location == token.Location && authority.KeyID == token.KeyID {
			return true
		}
	}
	return false
}

func copyIntSet(source map[int]bool) map[int]bool {
	result := make(map[int]bool, len(source))
	for value := range source {
		result[value] = true
	}
	return result
}

func copyStringSet(source map[string]bool) map[string]bool {
	result := make(map[string]bool, len(source))
	for value := range source {
		result[value] = true
	}
	return result
}

func findAssignment(primary Primary, discharges []Discharge, usable []bool, requireAll bool) (assignment, bool) {
	var visit func([]proofTask, map[int]bool, map[string]bool, []string, []int) (assignment, bool)
	visit = func(tasks []proofTask, used map[int]bool, usedReplay map[string]bool, sequence []string, indexes []int) (assignment, bool) {
		if len(tasks) == 0 {
			if requireAll && len(used) != len(discharges) {
				return assignment{}, false
			}
			return assignment{InstanceIDs: sequence, Indexes: indexes}, true
		}
		task := tasks[0]
		caveat := task.Caveat
		candidates := []int{}
		for i, token := range discharges {
			replayKey := dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)
			if used[i] || usedReplay[replayKey] || !usable[i] || token.Identifier != caveat.CaveatID {
				continue
			}
			matchesAuthority := caveat.Type == "third_party" && token.Location == caveat.Location && token.KeyID == caveat.KeyID
			if caveat.Type == "third_party_quorum" {
				matchesAuthority = authorityAllowed(caveat, token)
			}
			if matchesAuthority && attachmentMatches(task.ParentSignature, caveat, token.Signature, token.Attachment) {
				candidates = append(candidates, i)
			}
		}
		sort.Slice(candidates, func(i, j int) bool {
			return discharges[candidates[i]].InstanceID < discharges[candidates[j]].InstanceID
		})

		if caveat.Type == "third_party" {
			for _, index := range candidates {
				token := discharges[index]
				nextUsed := copyIntSet(used)
				nextReplay := copyStringSet(usedReplay)
				nextUsed[index] = true
				nextReplay[dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)] = true
				nextTasks := proofTasks(token.Caveats, token.Signature)
				nextTasks = append(nextTasks, tasks[1:]...)
				nextSequence := append(append([]string{}, sequence...), token.InstanceID)
				nextIndexes := append(append([]int{}, indexes...), index)
				if result, ok := visit(nextTasks, nextUsed, nextReplay, nextSequence, nextIndexes); ok {
					return result, true
				}
			}
			return assignment{}, false
		}

		combinations := [][]int{}
		var combine func(int, []int, map[string]bool, map[string]bool)
		combine = func(start int, chosen []int, authorities, replayIDs map[string]bool) {
			if len(chosen) == caveat.Threshold {
				combinations = append(combinations, append([]int{}, chosen...))
				return
			}
			for position := start; position < len(candidates); position++ {
				index := candidates[position]
				token := discharges[index]
				authorityKey := token.Location + "\x00" + token.KeyID
				replayKey := dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)
				if authorities[authorityKey] || replayIDs[replayKey] {
					continue
				}
				nextAuthorities := copyStringSet(authorities)
				nextReplayIDs := copyStringSet(replayIDs)
				nextAuthorities[authorityKey] = true
				nextReplayIDs[replayKey] = true
				combine(position+1, append(chosen, index), nextAuthorities, nextReplayIDs)
			}
		}
		combine(0, nil, map[string]bool{}, map[string]bool{})
		for _, chosen := range combinations {
			nextUsed := copyIntSet(used)
			nextReplay := copyStringSet(usedReplay)
			nextSequence := append([]string{}, sequence...)
			nextIndexes := append([]int{}, indexes...)
			nextTasks := []proofTask{}
			for _, index := range chosen {
				token := discharges[index]
				nextUsed[index] = true
				nextReplay[dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)] = true
				nextSequence = append(nextSequence, token.InstanceID)
				nextIndexes = append(nextIndexes, index)
				nextTasks = append(nextTasks, proofTasks(token.Caveats, token.Signature)...)
			}
			nextTasks = append(nextTasks, tasks[1:]...)
			if result, ok := visit(nextTasks, nextUsed, nextReplay, nextSequence, nextIndexes); ok {
				return result, true
			}
		}
		return assignment{}, false
	}
	return visit(proofTasks(primary.Caveats, primary.Signature), map[int]bool{}, map[string]bool{}, []string{}, []int{})
}

func skewExceeded(a, b, limit int64) bool {
	if limit < 0 {
		return true
	}
	var distance uint64
	if a >= b {
		distance = uint64(a) - uint64(b)
	} else {
		distance = uint64(b) - uint64(a)
	}
	return distance > uint64(limit)
}

func buildReport(input Input) Report {
	roots := map[string]Key{}
	for _, key := range input.RootKeys {
		roots[key.ID] = key
	}
	revoked := map[string]bool{}
	for _, identifier := range input.RevokedIdentifiers {
		revoked[identifier] = true
	}
	seen := map[string]bool{}
	reservedNonces := append([]NonceRef{}, input.ReservedNonces...)
	for _, nonce := range reservedNonces {
		seen[nonce.Identifier+"\x00"+nonce.Nonce] = true
	}
	spent := map[string]bool{}
	spentDischarges := append([]DischargeRef{}, input.SpentDischarges...)
	for _, discharge := range spentDischarges {
		spent[dischargeReplayKey(discharge.Location, discharge.KeyID, discharge.ReplayID)] = true
	}
	decisions := make([]Decision, 0, len(input.Requests))
	counts := map[string]int{}
	allowed, denied := 0, 0

	for _, req := range input.Requests {
		norm := normalizeRequest(req)
		found := map[string]bool{}
		key, known := roots[req.Macaroon.RootKeyID]
		authenticated := false
		if !known {
			found["unknown_root_key"] = true
		} else {
			if req.Timestamp < key.NotBefore || req.Timestamp > key.NotAfter {
				found["root_key_inactive"] = true
			}
			authenticated = secureHexEqual(req.Macaroon.Signature, primarySignature(key.Secret, req.Macaroon))
			if !authenticated {
				found["bad_primary_signature"] = true
			}
		}
		if revoked[req.Macaroon.Identifier] {
			found["revoked_identifier"] = true
		}
		if skewExceeded(input.EvaluationTime, req.Timestamp, input.MaxSkewSeconds) {
			found["timestamp_skew"] = true
		}

		dischargeResults, usable := auditDischarges(input, req, norm, revoked, spent)
		usedDischarges := []string{}
		if authenticated {
			replayKey := req.Macaroon.Identifier + "\x00" + req.Nonce
			if seen[replayKey] {
				found["replayed_nonce"] = true
			} else {
				reservedNonces = append(reservedNonces, NonceRef{Identifier: req.Macaroon.Identifier, Nonce: req.Nonce})
			}
			seen[replayKey] = true
			if !firstPartyOK(req.Macaroon.Caveats, req, norm) {
				found["first_party_unsatisfied"] = true
			}
			partial, partialOK := findAssignment(req.Macaroon, req.Discharges, usable, false)
			complete, completeOK := findAssignment(req.Macaroon, req.Discharges, usable, true)
			if !partialOK {
				found["third_party_unsatisfied"] = true
			}
			if !completeOK {
				found["unused_discharge"] = true
			}
			chosen := assignment{}
			chosenOK := false
			if completeOK {
				chosen = complete
				chosenOK = true
			} else if partialOK {
				chosen = partial
				chosenOK = true
			}
			if chosenOK {
				usedDischarges = chosen.InstanceIDs
			}
			for _, index := range chosen.Indexes {
				token := req.Discharges[index]
				key := dischargeReplayKey(token.Location, token.KeyID, token.ReplayID)
				if !spent[key] {
					spent[key] = true
					spentDischarges = append(spentDischarges, DischargeRef{
						Location: token.Location, KeyID: token.KeyID, ReplayID: token.ReplayID,
					})
				}
			}
		}
		reasons := orderedReasons(found, primaryOrder)
		decision := "allow"
		if len(reasons) > 0 {
			decision = "deny"
			denied++
		} else {
			allowed++
		}
		for _, reason := range reasons {
			counts[reason]++
		}
		payloads := make([]string, 0, len(req.Macaroon.Caveats))
		for _, caveat := range req.Macaroon.Caveats {
			payloads = append(payloads, canonicalCaveat(caveat))
		}
		decisions = append(decisions, Decision{
			ID: req.ID, Decision: decision, Reasons: reasons, Normalized: norm,
			PrimaryCaveats: payloads, UsedDischarges: usedDischarges, DischargeResults: dischargeResults,
		})
	}
	return Report{
		EvaluatedAt: input.EvaluationTime,
		Decisions:   decisions,
		Summary:     Summary{Allowed: allowed, Denied: denied, ReasonCounts: counts},
		FinalState:  FinalState{ReservedNonces: reservedNonces, SpentDischarges: spentDischarges},
	}
}

func main() {
	data, err := os.ReadFile("/app/input/inspection.json")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var input Input
	if err := json.Unmarshal(data, &input); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	report := buildReport(input)
	encoded, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.MkdirAll("/app/output", 0755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	if err := os.WriteFile("/app/output/report.json", encoded, 0644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}
