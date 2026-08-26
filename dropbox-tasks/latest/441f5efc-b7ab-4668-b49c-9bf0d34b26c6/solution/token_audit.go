package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type Issuer struct {
	ID   string
	Skew int64
}

type Key struct {
	ID        string
	Issuer    string
	Alg       string
	NotBefore int64
	NotAfter  int64
	Status    string
}

type Client struct {
	ID          string
	Issuer      string
	Status      string
	Tier        int64
	MaxTTL      int64
	RequirePKCE bool
	RequireDPOP bool
	Grants      map[string]bool
	Audiences   map[string]bool
}

type Resource struct {
	Audience string
	MinTier  int64
	Scopes   map[string]bool
}

type Action struct {
	ID         string
	Type       string
	Target     string
	Impact     int64
	Confidence int64
}

type ActionConflict struct {
	A string
	B string
}

type ActionPrerequisite struct {
	Child  string
	Parent string
}

type ActionBonus struct {
	A     string
	B     string
	Delta int64
}

type RemediationConfig struct {
	MaxActions           int
	MaxImpact            int64
	MinConfidence        int64
	Actions              []Action
	Conflicts            []ActionConflict
	Prerequisites        []ActionPrerequisite
	TypeLimits           map[string]int
	CoveredClientPenalty int64
	CoveredRootPenalty   int64
	Bonuses              []ActionBonus
}

type Event struct {
	ID              string
	Ts              int64
	Shard           string
	Seq             int64
	Client          string
	Subject         string
	Op              string
	JTI             string
	Parent          string
	Key             string
	Alg             string
	Grant           string
	Audience        string
	Scopes          []string
	ScopeSet        map[string]bool
	TTL             int64
	PKCE            string
	DPOP            string
	Nonce           string
	Depth           int64
	RootGrant       string
	RootPKCEGap     bool
	LineageWeakDPOP bool
}

type Case struct {
	Version          string
	Now              int64
	Issuers          map[string]Issuer
	Keys             map[string]Key
	Clients          map[string]Client
	Resources        map[string]Resource
	MaxExchangeDepth int64
	MaxChainLifetime int64
	Events           []Event
	Retractions      map[string]bool
	Remediation      RemediationConfig
}

type Token struct {
	JTI             string
	Client          string
	Subject         string
	Audience        string
	Scopes          []string
	ScopeSet        map[string]bool
	Expires         int64
	Key             string
	Risk            int64
	Revoked         bool
	RootJTI         string
	Depth           int64
	RootIssuedAt    int64
	RootGrant       string
	RootPKCEGap     bool
	LineageWeakDPOP bool
	ParentJTI       string
}

type Totals struct {
	Issued         int   `json:"issued"`
	RejectedEvents int   `json:"rejected_events"`
	Active         int   `json:"active"`
	Revoked        int   `json:"revoked"`
	Risk           int64 `json:"risk"`
}

type ActiveRow struct {
	JTI       string   `json:"jti"`
	Client    string   `json:"client"`
	Subject   string   `json:"subject"`
	Audience  string   `json:"audience"`
	Scopes    []string `json:"scopes"`
	ExpiresAt int64    `json:"expires_at"`
	Key       string   `json:"key"`
	Root      string   `json:"root"`
	Depth     int64    `json:"depth"`
	Risk      int64    `json:"risk"`
}

type RejectedRow struct {
	Event   string   `json:"event"`
	Reasons []string `json:"reasons"`
}

type ClientRow struct {
	Client         string `json:"client"`
	Issued         int    `json:"issued"`
	Active         int    `json:"active"`
	RejectedEvents int    `json:"rejected_events"`
	Risk           int64  `json:"risk"`
}

type RemediationTotals struct {
	Actions       int   `json:"actions"`
	Impact        int64 `json:"impact"`
	CoveredTokens int   `json:"covered_tokens"`
	Confidence    int64 `json:"confidence"`
}

type SelectedActionRow struct {
	ID         string   `json:"id"`
	Type       string   `json:"type"`
	Target     string   `json:"target"`
	Covers     []string `json:"covers"`
	Impact     int64    `json:"impact"`
	Confidence int64    `json:"confidence"`
}

type RejectedActionRow struct {
	ID      string   `json:"id"`
	Reasons []string `json:"reasons"`
}

type RemediationReport struct {
	Score        int64               `json:"score"`
	ResidualRisk int64               `json:"residual_risk"`
	Totals       RemediationTotals   `json:"totals"`
	Selected     []SelectedActionRow `json:"selected"`
	Rejected     []RejectedActionRow `json:"rejected"`
}

type Report struct {
	Now         int64             `json:"now"`
	Totals      Totals            `json:"totals"`
	Active      []ActiveRow       `json:"active"`
	Rejected    []RejectedRow     `json:"rejected"`
	Clients     []ClientRow       `json:"clients"`
	Remediation RemediationReport `json:"remediation"`
}

type clientStats struct {
	issued   int
	active   int
	rejected int
	risk     int64
}

type parser struct {
	tokens []string
	pos    int
}

type actionCandidate struct {
	Action Action
	Covers []string
}

type planChoice struct {
	Selected []int
	Score    int64
	Covered  int
	Impact   int64
	Conf     int64
	IDs      []string
}

func newParser(data string) *parser {
	return &parser{tokens: strings.Fields(data)}
}

func (p *parser) take() string {
	if p.pos >= len(p.tokens) {
		panic("unexpected end of input")
	}
	value := p.tokens[p.pos]
	p.pos++
	return value
}

func (p *parser) expect(expected string) {
	value := p.take()
	if value != expected {
		panic(fmt.Sprintf("expected %s, got %s", expected, value))
	}
}

func (p *parser) int64() int64 {
	value, err := strconv.ParseInt(p.take(), 10, 64)
	if err != nil {
		panic(err)
	}
	return value
}

func boolYes(value string) bool {
	return value == "yes"
}

func csvSet(value string) (map[string]bool, []string) {
	out := map[string]bool{}
	if value == "-" {
		return out, []string{}
	}
	for _, item := range strings.Split(value, ",") {
		if item == "" {
			continue
		}
		out[item] = true
	}
	keys := make([]string, 0, len(out))
	for key := range out {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return out, keys
}

func subset(a map[string]bool, b map[string]bool) bool {
	for item := range a {
		if !b[item] {
			return false
		}
	}
	return true
}

func parseCase(path string) Case {
	raw, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	p := newParser(string(raw))
	p.expect("OIDC_EXCHANGE_AUDIT")
	version := p.take()
	c := Case{
		Version:     version,
		Issuers:     map[string]Issuer{},
		Keys:        map[string]Key{},
		Clients:     map[string]Client{},
		Resources:   map[string]Resource{},
		Retractions: map[string]bool{},
		Remediation: RemediationConfig{
			TypeLimits: map[string]int{},
		},
	}
	p.expect("NOW")
	c.Now = p.int64()

	p.expect("ISSUERS")
	issuerCount := p.int64()
	for i := int64(0); i < issuerCount; i++ {
		p.expect("ISSUER")
		id := p.take()
		c.Issuers[id] = Issuer{ID: id, Skew: p.int64()}
	}

	p.expect("KEYS")
	keyCount := p.int64()
	for i := int64(0); i < keyCount; i++ {
		p.expect("KEY")
		id := p.take()
		c.Keys[id] = Key{
			ID:        id,
			Issuer:    p.take(),
			Alg:       p.take(),
			NotBefore: p.int64(),
			NotAfter:  p.int64(),
			Status:    p.take(),
		}
	}

	p.expect("CLIENTS")
	clientCount := p.int64()
	for i := int64(0); i < clientCount; i++ {
		p.expect("CLIENT")
		id := p.take()
		issuer := p.take()
		status := p.take()
		tier := p.int64()
		maxTTL := p.int64()
		requirePKCE := boolYes(p.take())
		requireDPOP := boolYes(p.take())
		grants, _ := csvSet(p.take())
		audiences, _ := csvSet(p.take())
		c.Clients[id] = Client{
			ID:          id,
			Issuer:      issuer,
			Status:      status,
			Tier:        tier,
			MaxTTL:      maxTTL,
			RequirePKCE: requirePKCE,
			RequireDPOP: requireDPOP,
			Grants:      grants,
			Audiences:   audiences,
		}
	}

	p.expect("RESOURCES")
	resourceCount := p.int64()
	for i := int64(0); i < resourceCount; i++ {
		p.expect("RESOURCE")
		aud := p.take()
		minTier := p.int64()
		scopes, _ := csvSet(p.take())
		c.Resources[aud] = Resource{Audience: aud, MinTier: minTier, Scopes: scopes}
	}

	p.expect("POLICY")
	c.MaxExchangeDepth = p.int64()
	c.MaxChainLifetime = p.int64()

	p.expect("EVENTS")
	eventCount := p.int64()
	for i := int64(0); i < eventCount; i++ {
		p.expect("EVENT")
		ev := Event{
			ID:      p.take(),
			Ts:      p.int64(),
			Shard:   p.take(),
			Seq:     p.int64(),
			Client:  p.take(),
			Subject: p.take(),
			Op:      p.take(),
		}
		switch ev.Op {
		case "MINT":
			ev.JTI = p.take()
			ev.Key = p.take()
			ev.Alg = p.take()
			ev.Grant = p.take()
			ev.Audience = p.take()
			ev.ScopeSet, ev.Scopes = csvSet(p.take())
			ev.TTL = p.int64()
			ev.PKCE = p.take()
			ev.DPOP = p.take()
			ev.Nonce = p.take()
		case "EXCHANGE":
			ev.JTI = p.take()
			ev.Parent = p.take()
			ev.Key = p.take()
			ev.Alg = p.take()
			ev.Grant = "exchange"
			ev.Audience = p.take()
			ev.ScopeSet, ev.Scopes = csvSet(p.take())
			ev.TTL = p.int64()
			ev.DPOP = p.take()
			ev.Nonce = p.take()
		case "REVOKE":
			ev.JTI = p.take()
		default:
			panic("unknown operation " + ev.Op)
		}
		c.Events = append(c.Events, ev)
	}

	if c.Version != "1" {
		p.expect("RETRACTIONS")
		retractionCount := p.int64()
		for i := int64(0); i < retractionCount; i++ {
			p.expect("RETRACT")
			c.Retractions[p.take()] = true
		}
	}

	p.expect("REMEDIATION")
	c.Remediation.MaxActions = int(p.int64())
	c.Remediation.MaxImpact = p.int64()
	c.Remediation.MinConfidence = p.int64()

	p.expect("ACTIONS")
	actionCount := p.int64()
	for i := int64(0); i < actionCount; i++ {
		p.expect("ACTION")
		c.Remediation.Actions = append(c.Remediation.Actions, Action{
			ID:         p.take(),
			Type:       p.take(),
			Target:     p.take(),
			Impact:     p.int64(),
			Confidence: p.int64(),
		})
	}

	p.expect("ACTION_CONFLICTS")
	conflictCount := p.int64()
	for i := int64(0); i < conflictCount; i++ {
		p.expect("ACTION_CONFLICT")
		c.Remediation.Conflicts = append(c.Remediation.Conflicts, ActionConflict{A: p.take(), B: p.take()})
	}

	p.expect("ACTION_PREREQUISITES")
	prereqCount := p.int64()
	for i := int64(0); i < prereqCount; i++ {
		p.expect("ACTION_PREREQ")
		c.Remediation.Prerequisites = append(c.Remediation.Prerequisites, ActionPrerequisite{Child: p.take(), Parent: p.take()})
	}

	if c.Version == "3" {
		p.expect("ACTION_TYPE_LIMITS")
		typeLimitCount := p.int64()
		for i := int64(0); i < typeLimitCount; i++ {
			p.expect("ACTION_TYPE_LIMIT")
			c.Remediation.TypeLimits[p.take()] = int(p.int64())
		}
		p.expect("PLAN_TUNING")
		c.Remediation.CoveredClientPenalty = p.int64()
		c.Remediation.CoveredRootPenalty = p.int64()
		p.expect("ACTION_BONUSES")
		bonusCount := p.int64()
		for i := int64(0); i < bonusCount; i++ {
			p.expect("ACTION_BONUS")
			c.Remediation.Bonuses = append(c.Remediation.Bonuses, ActionBonus{
				A:     p.take(),
				B:     p.take(),
				Delta: p.int64(),
			})
		}
	}

	p.expect("END")
	if p.pos != len(p.tokens) {
		panic("trailing tokens")
	}
	return c
}

func orderedEvents(c Case) []Event {
	events := make([]Event, 0, len(c.Events))
	for _, ev := range c.Events {
		if c.Retractions[ev.ID] {
			continue
		}
		events = append(events, ev)
	}
	sort.Slice(events, func(i, j int) bool {
		a, b := events[i], events[j]
		if a.Ts != b.Ts {
			return a.Ts < b.Ts
		}
		if a.Shard != b.Shard {
			return a.Shard < b.Shard
		}
		if a.Seq != b.Seq {
			return a.Seq < b.Seq
		}
		return a.ID < b.ID
	})
	return events
}

func keyActive(c Case, key Key, ev Event, client Client, clientOK bool) bool {
	skew := int64(0)
	if issuer, ok := c.Issuers[key.Issuer]; ok {
		skew = issuer.Skew
	}
	if key.Status != "active" {
		return false
	}
	if clientOK && key.Issuer != client.Issuer {
		return false
	}
	return key.NotBefore-skew <= ev.Ts && ev.Ts <= key.NotAfter+skew
}

func tokenReasons(c Case, ev Event, tokens map[string]*Token, nonces map[string]map[string]bool) []string {
	reasons := []string{}
	client, clientOK := c.Clients[ev.Client]
	if !clientOK {
		reasons = append(reasons, "unknown_client")
	} else if client.Status != "active" {
		reasons = append(reasons, "client_disabled")
	}

	key, keyOK := c.Keys[ev.Key]
	if !keyOK {
		reasons = append(reasons, "unknown_key")
	} else {
		if !keyActive(c, key, ev, client, clientOK) {
			reasons = append(reasons, "key_inactive")
		}
		if ev.Alg != key.Alg {
			reasons = append(reasons, "alg_mismatch")
		}
	}

	resource, resourceOK := c.Resources[ev.Audience]
	if !resourceOK {
		reasons = append(reasons, "unknown_resource")
	}
	if clientOK && resourceOK && client.Tier < resource.MinTier {
		reasons = append(reasons, "tier_insufficient")
	}
	if clientOK && !client.Grants[ev.Grant] {
		reasons = append(reasons, "grant_not_allowed")
	}
	if clientOK && !client.Audiences[ev.Audience] {
		reasons = append(reasons, "audience_not_allowed")
	}
	if resourceOK && !subset(ev.ScopeSet, resource.Scopes) {
		reasons = append(reasons, "scope_not_allowed")
	}
	if clientOK && ev.TTL > client.MaxTTL {
		reasons = append(reasons, "ttl_exceeded")
	}
	if ev.Op == "MINT" && clientOK && client.RequirePKCE && ev.PKCE != "yes" {
		reasons = append(reasons, "pkce_required")
	}
	if clientOK && client.RequireDPOP && ev.DPOP != "yes" {
		reasons = append(reasons, "dpop_required")
	}

	if ev.Op == "EXCHANGE" {
		parent, parentOK := tokens[ev.Parent]
		if !parentOK {
			reasons = append(reasons, "parent_missing")
		} else {
			if parent.Revoked || ev.Ts >= parent.Expires {
				reasons = append(reasons, "parent_inactive")
			}
			if parent.Client != ev.Client || parent.Subject != ev.Subject {
				reasons = append(reasons, "subject_mismatch")
			}
			if !subset(ev.ScopeSet, parent.ScopeSet) {
				reasons = append(reasons, "scope_escalation")
			}
			if parent.Depth+1 > c.MaxExchangeDepth {
				reasons = append(reasons, "depth_exceeded")
			}
			if ev.Ts+ev.TTL > parent.RootIssuedAt+c.MaxChainLifetime {
				reasons = append(reasons, "chain_expiry_exceeded")
			}
		}
	}

	if ev.Nonce != "-" {
		nonceKey := ev.Client + "\x00" + ev.Subject
		if nonces[nonceKey] != nil && nonces[nonceKey][ev.Nonce] {
			reasons = append(reasons, "replay_nonce")
		}
	}
	return reasons
}

func tokenRisk(c Case, ev Event) int64 {
	resource := c.Resources[ev.Audience]
	risk := ev.TTL + 5*int64(len(ev.Scopes)) + 10*resource.MinTier
	switch ev.Grant {
	case "password":
		risk += 100
	case "client_credentials":
		risk += 25
	case "exchange":
		risk += 40
	default:
		risk += 10
	}
	if ev.DPOP == "no" {
		risk += 40
	}
	if ev.Op == "MINT" && ev.PKCE == "no" {
		risk += 20
	}
	risk += 15 * ev.Depth
	switch ev.RootGrant {
	case "password":
		risk += 35
	case "client_credentials":
		risk += 15
	}
	if ev.LineageWeakDPOP {
		risk += 20
	}
	if ev.RootPKCEGap {
		risk += 10
	}
	return risk
}

func activeTokenMap(c Case, tokens map[string]*Token) map[string]*Token {
	active := map[string]*Token{}
	for jti, token := range tokens {
		if !token.Revoked && c.Now < token.Expires {
			active[jti] = token
		}
	}
	return active
}

func sortedKeys(m map[string]bool) []string {
	keys := make([]string, 0, len(m))
	for key := range m {
		keys = append(keys, key)
	}
	sort.Strings(keys)
	return keys
}

func isDescendant(token *Token, ancestorJTI string, tokens map[string]*Token) bool {
	current := token
	for current != nil {
		if current.JTI == ancestorJTI {
			return true
		}
		if current.ParentJTI == "" {
			return false
		}
		current = tokens[current.ParentJTI]
	}
	return false
}

func actionCovers(c Case, action Action, tokens map[string]*Token, active map[string]*Token) (bool, []string) {
	covered := map[string]bool{}
	targetKnown := false

	switch action.Type {
	case "REVOKE_TOKEN":
		if _, ok := tokens[action.Target]; ok {
			targetKnown = true
			if active[action.Target] != nil {
				covered[action.Target] = true
			}
		}
	case "REVOKE_LINEAGE":
		if _, ok := tokens[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if isDescendant(token, action.Target, tokens) {
					covered[jti] = true
				}
			}
		}
	case "DISABLE_CLIENT":
		if _, ok := c.Clients[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Client == action.Target {
					covered[jti] = true
				}
			}
		}
	case "RETIRE_KEY":
		if _, ok := c.Keys[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Key == action.Target {
					covered[jti] = true
				}
			}
		}
	case "QUARANTINE_SUBJECT":
		for _, token := range tokens {
			if token.Subject == action.Target {
				targetKnown = true
				break
			}
		}
		if targetKnown {
			for jti, token := range active {
				if token.Subject == action.Target {
					covered[jti] = true
				}
			}
		}
	case "LIMIT_AUDIENCE":
		if _, ok := c.Resources[action.Target]; ok {
			targetKnown = true
			for jti, token := range active {
				if token.Audience == action.Target {
					covered[jti] = true
				}
			}
		}
	}
	return targetKnown, sortedKeys(covered)
}

func actionReasons(c Case, action Action, tokens map[string]*Token, active map[string]*Token) ([]string, []string) {
	reasons := []string{}
	knownType := map[string]bool{
		"REVOKE_TOKEN":       true,
		"REVOKE_LINEAGE":     true,
		"DISABLE_CLIENT":     true,
		"RETIRE_KEY":         true,
		"QUARANTINE_SUBJECT": true,
		"LIMIT_AUDIENCE":     true,
	}[action.Type]
	if !knownType {
		reasons = append(reasons, "unknown_action_type")
	} else {
		targetKnown, covers := actionCovers(c, action, tokens, active)
		if !targetKnown {
			reasons = append(reasons, "unknown_target")
		} else if len(covers) == 0 {
			reasons = append(reasons, "no_active_coverage")
		}
		if action.Confidence < c.Remediation.MinConfidence {
			reasons = append(reasons, "low_confidence")
		}
		if action.Impact > c.Remediation.MaxImpact {
			reasons = append(reasons, "impact_exceeds_budget")
		}
		return reasons, covers
	}
	if action.Confidence < c.Remediation.MinConfidence {
		reasons = append(reasons, "low_confidence")
	}
	if action.Impact > c.Remediation.MaxImpact {
		reasons = append(reasons, "impact_exceeds_budget")
	}
	return reasons, []string{}
}

func conflictKey(a, b string) string {
	if a > b {
		a, b = b, a
	}
	return a + "\x00" + b
}

func lexLess(a, b []string) bool {
	for i := 0; i < len(a) && i < len(b); i++ {
		if a[i] != b[i] {
			return a[i] < b[i]
		}
	}
	return len(a) < len(b)
}

func betterPlan(a, b planChoice) bool {
	if a.Score != b.Score {
		return a.Score > b.Score
	}
	if a.Covered != b.Covered {
		return a.Covered > b.Covered
	}
	if a.Impact != b.Impact {
		return a.Impact < b.Impact
	}
	if a.Conf != b.Conf {
		return a.Conf > b.Conf
	}
	if len(a.Selected) != len(b.Selected) {
		return len(a.Selected) < len(b.Selected)
	}
	return lexLess(a.IDs, b.IDs)
}

func evaluatePlan(c Case, selected []int, candidates []actionCandidate, active map[string]*Token) planChoice {
	covered := map[string]bool{}
	coveredClients := map[string]bool{}
	coveredRoots := map[string]bool{}
	selectedIDs := map[string]bool{}
	choice := planChoice{Selected: append([]int{}, selected...)}
	for _, idx := range selected {
		action := candidates[idx].Action
		choice.Impact += action.Impact
		choice.Conf += action.Confidence
		choice.IDs = append(choice.IDs, action.ID)
		selectedIDs[action.ID] = true
		for _, jti := range candidates[idx].Covers {
			covered[jti] = true
		}
	}
	sort.Strings(choice.IDs)
	for jti := range covered {
		token := active[jti]
		choice.Score += token.Risk
		coveredClients[token.Client] = true
		coveredRoots[token.RootJTI] = true
	}
	for _, bonus := range c.Remediation.Bonuses {
		if selectedIDs[bonus.A] && selectedIDs[bonus.B] {
			choice.Score += bonus.Delta
		}
	}
	choice.Score -= c.Remediation.CoveredClientPenalty * int64(len(coveredClients))
	choice.Score -= c.Remediation.CoveredRootPenalty * int64(len(coveredRoots))
	choice.Covered = len(covered)
	return choice
}

func buildRemediation(c Case, tokens map[string]*Token, totalRisk int64) RemediationReport {
	active := activeTokenMap(c, tokens)
	rejected := []RejectedActionRow{}
	candidates := []actionCandidate{}

	for _, action := range c.Remediation.Actions {
		reasons, covers := actionReasons(c, action, tokens, active)
		if len(reasons) > 0 {
			rejected = append(rejected, RejectedActionRow{ID: action.ID, Reasons: reasons})
			continue
		}
		candidates = append(candidates, actionCandidate{Action: action, Covers: covers})
	}
	sort.Slice(rejected, func(i, j int) bool { return rejected[i].ID < rejected[j].ID })

	conflicts := map[string]bool{}
	for _, pair := range c.Remediation.Conflicts {
		conflicts[conflictKey(pair.A, pair.B)] = true
	}
	candidateIndex := map[string]int{}
	for idx, candidate := range candidates {
		candidateIndex[candidate.Action.ID] = idx
	}
	prerequisites := map[int]map[int]bool{}
	for _, edge := range c.Remediation.Prerequisites {
		childIdx, childOK := candidateIndex[edge.Child]
		parentIdx, parentOK := candidateIndex[edge.Parent]
		if !childOK || !parentOK {
			continue
		}
		if prerequisites[childIdx] == nil {
			prerequisites[childIdx] = map[int]bool{}
		}
		prerequisites[childIdx][parentIdx] = true
	}

	closure := func(selected []int) []int {
		out := map[int]bool{}
		stack := append([]int{}, selected...)
		for len(stack) > 0 {
			last := stack[len(stack)-1]
			stack = stack[:len(stack)-1]
			if out[last] {
				continue
			}
			out[last] = true
			for parent := range prerequisites[last] {
				if !out[parent] {
					stack = append(stack, parent)
				}
			}
		}
		result := make([]int, 0, len(out))
		for idx := range out {
			result = append(result, idx)
		}
		sort.Ints(result)
		return result
	}

	validSelection := func(selected []int) bool {
		if len(selected) > c.Remediation.MaxActions {
			return false
		}
		impact := int64(0)
		typeCounts := map[string]int{}
		for _, idx := range selected {
			action := candidates[idx].Action
			impact += action.Impact
			typeCounts[action.Type]++
		}
		if impact > c.Remediation.MaxImpact {
			return false
		}
		for actionType, limit := range c.Remediation.TypeLimits {
			if typeCounts[actionType] > limit {
				return false
			}
		}
		for i := 0; i < len(selected); i++ {
			for j := i + 1; j < len(selected); j++ {
				if conflicts[conflictKey(candidates[selected[i]].Action.ID, candidates[selected[j]].Action.ID)] {
					return false
				}
			}
		}
		return true
	}

	best := evaluatePlan(c, nil, candidates, active)
	seen := map[string]bool{}
	var dfs func(int, []int)
	dfs = func(pos int, selected []int) {
		keyParts := make([]string, len(selected))
		for i, idx := range selected {
			keyParts[i] = strconv.Itoa(idx)
		}
		stateKey := fmt.Sprintf("%d|%s", pos, strings.Join(keyParts, ","))
		if seen[stateKey] {
			return
		}
		seen[stateKey] = true

		if pos == len(candidates) {
			choice := evaluatePlan(c, selected, candidates, active)
			if betterPlan(choice, best) {
				best = choice
			}
			return
		}

		dfs(pos+1, selected)

		next := closure(append(append([]int{}, selected...), pos))
		if !validSelection(next) {
			return
		}
		dfs(pos+1, next)
	}
	dfs(0, nil)

	selectedRows := []SelectedActionRow{}
	for _, idx := range best.Selected {
		candidate := candidates[idx]
		selectedRows = append(selectedRows, SelectedActionRow{
			ID:         candidate.Action.ID,
			Type:       candidate.Action.Type,
			Target:     candidate.Action.Target,
			Covers:     append([]string{}, candidate.Covers...),
			Impact:     candidate.Action.Impact,
			Confidence: candidate.Action.Confidence,
		})
	}
	sort.Slice(selectedRows, func(i, j int) bool { return selectedRows[i].ID < selectedRows[j].ID })

	return RemediationReport{
		Score:        best.Score,
		ResidualRisk: totalRisk - best.Score,
		Totals: RemediationTotals{
			Actions:       len(best.Selected),
			Impact:        best.Impact,
			CoveredTokens: best.Covered,
			Confidence:    best.Conf,
		},
		Selected: selectedRows,
		Rejected: rejected,
	}
}

func audit(c Case) Report {
	stats := map[string]*clientStats{}
	clientIDs := make([]string, 0, len(c.Clients))
	for id := range c.Clients {
		stats[id] = &clientStats{}
		clientIDs = append(clientIDs, id)
	}
	sort.Strings(clientIDs)

	tokens := map[string]*Token{}
	nonces := map[string]map[string]bool{}
	seenEvents := map[string]bool{}
	rejected := []RejectedRow{}
	issued := 0

	addRejected := func(ev Event, reasons []string) {
		rejected = append(rejected, RejectedRow{Event: ev.ID, Reasons: reasons})
		if st := stats[ev.Client]; st != nil {
			st.rejected++
		}
	}

	for _, ev := range orderedEvents(c) {
		if seenEvents[ev.ID] {
			addRejected(ev, []string{"duplicate_event"})
			continue
		}
		seenEvents[ev.ID] = true

		switch ev.Op {
		case "MINT", "EXCHANGE":
			reasons := tokenReasons(c, ev, tokens, nonces)
			if len(reasons) > 0 {
				addRejected(ev, reasons)
				continue
			}
			rootJTI := ev.JTI
			depth := int64(0)
			rootIssuedAt := ev.Ts
			rootGrant := ev.Grant
			rootPKCEGap := ev.PKCE == "no"
			lineageWeakDPOP := ev.DPOP == "no"
			parentJTI := ""
			if ev.Op == "EXCHANGE" {
				parent := tokens[ev.Parent]
				rootJTI = parent.RootJTI
				depth = parent.Depth + 1
				rootIssuedAt = parent.RootIssuedAt
				rootGrant = parent.RootGrant
				rootPKCEGap = parent.RootPKCEGap
				lineageWeakDPOP = parent.LineageWeakDPOP || ev.DPOP == "no"
				parentJTI = ev.Parent
			}
			ev.Depth = depth
			ev.RootGrant = rootGrant
			ev.RootPKCEGap = rootPKCEGap
			ev.LineageWeakDPOP = lineageWeakDPOP
			token := &Token{
				JTI:             ev.JTI,
				Client:          ev.Client,
				Subject:         ev.Subject,
				Audience:        ev.Audience,
				Scopes:          append([]string{}, ev.Scopes...),
				ScopeSet:        ev.ScopeSet,
				Expires:         ev.Ts + ev.TTL,
				Key:             ev.Key,
				Risk:            tokenRisk(c, ev),
				RootJTI:         rootJTI,
				Depth:           depth,
				RootIssuedAt:    rootIssuedAt,
				RootGrant:       rootGrant,
				RootPKCEGap:     rootPKCEGap,
				LineageWeakDPOP: lineageWeakDPOP,
				ParentJTI:       parentJTI,
			}
			tokens[ev.JTI] = token
			issued++
			stats[ev.Client].issued++
			if ev.Nonce != "-" {
				nonceKey := ev.Client + "\x00" + ev.Subject
				if nonces[nonceKey] == nil {
					nonces[nonceKey] = map[string]bool{}
				}
				nonces[nonceKey][ev.Nonce] = true
			}
		case "REVOKE":
			reasons := []string{}
			if _, ok := c.Clients[ev.Client]; !ok {
				reasons = append(reasons, "unknown_client")
			}
			token, tokenOK := tokens[ev.JTI]
			if !tokenOK {
				reasons = append(reasons, "token_missing")
			} else if token.Client != ev.Client || token.Subject != ev.Subject {
				reasons = append(reasons, "subject_mismatch")
			}
			if len(reasons) > 0 {
				addRejected(ev, reasons)
				continue
			}
			token.Revoked = true
		}
	}

	activeRows := []ActiveRow{}
	revoked := 0
	totalRisk := int64(0)
	for _, token := range tokens {
		if token.Revoked {
			revoked++
		}
		if !token.Revoked && c.Now < token.Expires {
			activeRows = append(activeRows, ActiveRow{
				JTI:       token.JTI,
				Client:    token.Client,
				Subject:   token.Subject,
				Audience:  token.Audience,
				Scopes:    append([]string{}, token.Scopes...),
				ExpiresAt: token.Expires,
				Key:       token.Key,
				Root:      token.RootJTI,
				Depth:     token.Depth,
				Risk:      token.Risk,
			})
			stats[token.Client].active++
			stats[token.Client].risk += token.Risk
			totalRisk += token.Risk
		}
	}
	sort.Slice(activeRows, func(i, j int) bool {
		return activeRows[i].JTI < activeRows[j].JTI
	})

	clientRows := make([]ClientRow, 0, len(clientIDs))
	for _, id := range clientIDs {
		st := stats[id]
		clientRows = append(clientRows, ClientRow{
			Client:         id,
			Issued:         st.issued,
			Active:         st.active,
			RejectedEvents: st.rejected,
			Risk:           st.risk,
		})
	}

	return Report{
		Now: c.Now,
		Totals: Totals{
			Issued:         issued,
			RejectedEvents: len(rejected),
			Active:         len(activeRows),
			Revoked:        revoked,
			Risk:           totalRisk,
		},
		Active:      activeRows,
		Rejected:    rejected,
		Clients:     clientRows,
		Remediation: buildRemediation(c, tokens, totalRisk),
	}
}

func main() {
	if len(os.Args) != 5 || os.Args[1] != "--input" || os.Args[3] != "--output" {
		fmt.Fprintln(os.Stderr, "usage: token_audit --input <case-file> --output <report-file>")
		os.Exit(2)
	}
	report := audit(parseCase(os.Args[2]))
	if err := os.MkdirAll(filepath.Dir(os.Args[4]), 0o755); err != nil {
		panic(err)
	}
	out, err := os.Create(os.Args[4])
	if err != nil {
		panic(err)
	}
	defer out.Close()
	enc := json.NewEncoder(out)
	enc.SetIndent("", "  ")
	if err := enc.Encode(report); err != nil {
		panic(err)
	}
}
