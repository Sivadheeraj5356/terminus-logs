package main

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"
)

type Policy struct {
	ApprovalWindow   int            `json:"approval_window"`
	ControlWindow    int            `json:"control_window"`
	MaxRouteHops     int            `json:"max_route_hops"`
	StepUpAfter      int            `json:"step_up_after"`
	DenyAbove        int            `json:"deny_above"`
	ClearanceOrder   []string       `json:"clearance_order"`
	RiskSignalScores map[string]int `json:"risk_signal_scores"`
}

type Principal struct {
	ID           string `json:"id"`
	Org          string `json:"org"`
	Site         string `json:"site"`
	Clearance    string `json:"clearance"`
	Secret       string `json:"secret"`
	Available    bool   `json:"available"`
	ActiveFrom   int    `json:"active_from"`
	ActiveUntil  int    `json:"active_until"`
	RevokedAfter int    `json:"revoked_after"`
	External     bool   `json:"external"`
}

type Resource struct {
	ID                 string     `json:"id"`
	Zone               string     `json:"zone"`
	MinClearance       string     `json:"min_clearance"`
	RequiredRoles      []string   `json:"required_roles"`
	RequiredControls   []string   `json:"required_controls"`
	MinDistinctOrgs    int        `json:"min_distinct_orgs"`
	MinDistinctSites   int        `json:"min_distinct_sites"`
	BaseRisk           int        `json:"base_risk"`
	SeparationPairs    [][]string `json:"separation_pairs"`
	OrgSeparationPairs [][]string `json:"org_separation_pairs"`
}

type Gateway struct {
	ID              string `json:"id"`
	FromZone        string `json:"from_zone"`
	ToZone          string `json:"to_zone"`
	InitiallyLocked bool   `json:"initially_locked"`
}

type Event struct {
	ID          string   `json:"id"`
	Revision    int      `json:"revision"`
	Time        int      `json:"time"`
	IngestSeq   int      `json:"ingest_seq"`
	Type        string   `json:"type"`
	Session     string   `json:"session"`
	Principal   string   `json:"principal"`
	Resource    string   `json:"resource"`
	Role        string   `json:"role"`
	Control     string   `json:"control"`
	Gateway     string   `json:"gateway"`
	FromZone    string   `json:"from_zone"`
	ToZone      string   `json:"to_zone"`
	Token       string   `json:"token"`
	Challenge   string   `json:"challenge"`
	ExpiresAt   int      `json:"expires_at"`
	RiskSignals []string `json:"risk_signals"`
	Signature   string   `json:"signature"`
}

type Case struct {
	Policy     Policy      `json:"policy"`
	Principals []Principal `json:"principals"`
	Resources  []Resource  `json:"resources"`
	Gateways   []Gateway   `json:"gateways"`
	Events     []Event     `json:"events"`
}

type EventFinding struct {
	ID      string   `json:"id"`
	Type    string   `json:"type"`
	Status  string   `json:"status"`
	Reasons []string `json:"reasons"`
}

type ProviderRow struct {
	Role      string   `json:"role,omitempty"`
	Control   string   `json:"control,omitempty"`
	Providers []string `json:"providers"`
}

type Decision struct {
	ID        string        `json:"id"`
	Session   string        `json:"session"`
	Resource  string        `json:"resource"`
	Status    string        `json:"status"`
	RiskScore int           `json:"risk_score"`
	Reasons   []string      `json:"reasons"`
	Approvals []ProviderRow `json:"approvals"`
	Controls  []ProviderRow `json:"controls"`
	Route     []string      `json:"route"`
}

type FinalSession struct {
	Session         string `json:"session"`
	Resource        string `json:"resource"`
	State           string `json:"state"`
	CurrentZone     string `json:"current_zone"`
	HopCount        int    `json:"hop_count"`
	ActivationCount int    `json:"activation_count"`
}

type Output struct {
	EventFindings    []EventFinding `json:"event_findings"`
	Decisions        []Decision     `json:"decisions"`
	FinalSessions    []FinalSession `json:"final_sessions"`
	ConsumedSessions []string       `json:"consumed_sessions"`
}

type Approval struct {
	EventID   string
	Role      string
	Principal string
	Time      int
}

type Control struct {
	EventID   string
	Control   string
	Principal string
	Time      int
}

type SessionState struct {
	ID              string
	Resource        string
	Challenge       string
	ExpiresAt       int
	OpenTime        int
	State           string
	CurrentZone     string
	HopCount        int
	ActivationCount int
	Consumed        bool
	Route           []string
	Approvals       []Approval
	Controls        []Control
}

var eventReasonOrder = []string{
	"principal_unavailable",
	"principal_inactive",
	"principal_revoked",
	"bad_signature",
	"session_missing",
	"session_closed",
	"session_expired",
	"challenge_mismatch",
	"duplicate_open",
	"role_not_required",
	"clearance_too_low",
	"control_not_required",
	"gateway_mismatch",
	"gateway_locked",
	"route_too_long",
}

var decisionReasonOrder = []string{
	"event_ignored",
	"token_replayed",
	"route_incomplete",
	"missing_quorum",
	"org_diversity",
	"site_diversity",
	"separation_violation",
	"missing_control",
	"risk_too_high",
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: breakglass-ledger input.json output.json")
		os.Exit(2)
	}
	data, err := os.ReadFile(os.Args[1])
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	var req Case
	if err := json.Unmarshal(data, &req); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	out := reconcile(req)
	if err := os.MkdirAll(filepath.Dir(os.Args[2]), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded, err := json.MarshalIndent(out, "", "  ")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	encoded = append(encoded, '\n')
	if err := os.WriteFile(os.Args[2], encoded, 0o644); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func reconcile(req Case) Output {
	principals := map[string]Principal{}
	for _, principal := range req.Principals {
		principals[principal.ID] = principal
	}
	resources := map[string]Resource{}
	for _, resource := range req.Resources {
		resources[resource.ID] = resource
	}
	gateways := map[string]Gateway{}
	gatewayLocked := map[string]bool{}
	for _, gateway := range req.Gateways {
		gateways[gateway.ID] = gateway
		gatewayLocked[gateway.ID] = gateway.InitiallyLocked
	}

	events := retainedEvents(req.Events)
	sessions := map[string]*SessionState{}
	findingsByEventID := map[string]EventFinding{}
	out := Output{
		EventFindings:    []EventFinding{},
		Decisions:        []Decision{},
		FinalSessions:    []FinalSession{},
		ConsumedSessions: []string{},
	}

	for _, event := range events {
		reasons := eventReasons(req, principals, resources, gateways, gatewayLocked, sessions, event)
		status := "accepted"
		if len(reasons) > 0 {
			status = "ignored"
		}
		finding := EventFinding{ID: event.ID, Type: event.Type, Status: status, Reasons: reasons}
		out.EventFindings = append(out.EventFindings, finding)
		findingsByEventID[event.ID] = finding

		if event.Type == "activate" {
			decision := buildDecision(req, principals, resources, sessions, event, finding)
			out.Decisions = append(out.Decisions, decision)
			if finding.Status == "accepted" && (decision.Status == "allow" || decision.Status == "step_up") {
				if session, ok := sessions[event.Session]; ok {
					session.Consumed = true
					session.ActivationCount++
					session.State = "activated"
				}
			}
		}

		if len(reasons) > 0 {
			continue
		}
		applyEvent(req, principals, gateways, gatewayLocked, sessions, event)
	}

	sessionIDs := make([]string, 0, len(sessions))
	for id := range sessions {
		sessionIDs = append(sessionIDs, id)
	}
	sort.Strings(sessionIDs)
	for _, id := range sessionIDs {
		session := sessions[id]
		out.FinalSessions = append(out.FinalSessions, FinalSession{
			Session:         session.ID,
			Resource:        session.Resource,
			State:           session.State,
			CurrentZone:     session.CurrentZone,
			HopCount:        session.HopCount,
			ActivationCount: session.ActivationCount,
		})
		if session.Consumed {
			out.ConsumedSessions = append(out.ConsumedSessions, session.ID)
		}
	}
	sort.Strings(out.ConsumedSessions)

	_ = findingsByEventID
	return out
}

func retainedEvents(events []Event) []Event {
	kept := map[string]Event{}
	for _, event := range events {
		current, ok := kept[event.ID]
		if !ok || betterEvent(event, current) {
			kept[event.ID] = event
		}
	}
	retained := make([]Event, 0, len(kept))
	for _, event := range kept {
		retained = append(retained, event)
	}
	sort.Slice(retained, func(i, j int) bool {
		left, right := retained[i], retained[j]
		if left.Time != right.Time {
			return left.Time < right.Time
		}
		if left.IngestSeq != right.IngestSeq {
			return left.IngestSeq < right.IngestSeq
		}
		return left.ID < right.ID
	})
	return retained
}

func betterEvent(candidate, current Event) bool {
	if candidate.Revision != current.Revision {
		return candidate.Revision > current.Revision
	}
	if candidate.Time != current.Time {
		return candidate.Time > current.Time
	}
	if candidate.IngestSeq != current.IngestSeq {
		return candidate.IngestSeq > current.IngestSeq
	}
	return candidate.Session < current.Session
}

func eventReasons(req Case, principals map[string]Principal, resources map[string]Resource, gateways map[string]Gateway, gatewayLocked map[string]bool, sessions map[string]*SessionState, event Event) []string {
	reasons := map[string]bool{}
	principal := principals[event.Principal]
	if !principal.Available {
		reasons["principal_unavailable"] = true
	}
	if event.Time < principal.ActiveFrom || event.Time > principal.ActiveUntil {
		reasons["principal_inactive"] = true
	}
	if principal.RevokedAfter != 0 && event.Time >= principal.RevokedAfter {
		reasons["principal_revoked"] = true
	}
	if !signatureOK(principal.Secret, event) {
		reasons["bad_signature"] = true
	}

	session, hasSession := sessions[event.Session]
	if usesSession(event.Type) {
		if !hasSession {
			reasons["session_missing"] = true
		} else {
			if session.State == "closed" {
				reasons["session_closed"] = true
			}
			if event.Time > session.ExpiresAt {
				reasons["session_expired"] = true
			}
			if event.Challenge != session.Challenge {
				reasons["challenge_mismatch"] = true
			}
		}
	}

	switch event.Type {
	case "open":
		if existing, ok := sessions[event.Session]; ok && existing.State != "closed" {
			reasons["duplicate_open"] = true
		}
	case "approve":
		if hasSession {
			resource := resources[session.Resource]
			if !contains(resource.RequiredRoles, event.Role) {
				reasons["role_not_required"] = true
			}
			if !clearanceOK(req.Policy, principal.Clearance, resource.MinClearance) {
				reasons["clearance_too_low"] = true
			}
		}
	case "control":
		if hasSession {
			resource := resources[session.Resource]
			if !contains(resource.RequiredControls, event.Control) {
				reasons["control_not_required"] = true
			}
		}
	case "hop":
		gateway, ok := gateways[event.Gateway]
		if !ok || gateway.FromZone != event.FromZone || gateway.ToZone != event.ToZone {
			reasons["gateway_mismatch"] = true
		}
		if hasSession && event.FromZone != session.CurrentZone {
			reasons["gateway_mismatch"] = true
		}
		if ok && gatewayLocked[event.Gateway] {
			reasons["gateway_locked"] = true
		}
		if hasSession && session.HopCount+1 > req.Policy.MaxRouteHops {
			reasons["route_too_long"] = true
		}
	case "lock", "unlock":
		gateway, ok := gateways[event.Gateway]
		if !ok || gateway.FromZone != event.FromZone || gateway.ToZone != event.ToZone {
			reasons["gateway_mismatch"] = true
		}
	}
	return orderedReasons(reasons, eventReasonOrder)
}

func usesSession(eventType string) bool {
	switch eventType {
	case "approve", "control", "hop", "activate", "close":
		return true
	default:
		return false
	}
}

func applyEvent(req Case, principals map[string]Principal, gateways map[string]Gateway, gatewayLocked map[string]bool, sessions map[string]*SessionState, event Event) {
	switch event.Type {
	case "open":
		principal := principals[event.Principal]
		sessions[event.Session] = &SessionState{
			ID:              event.Session,
			Resource:        event.Resource,
			Challenge:       event.Challenge,
			ExpiresAt:       event.ExpiresAt,
			OpenTime:        event.Time,
			State:           "open",
			CurrentZone:     principal.Site,
			HopCount:        0,
			ActivationCount: 0,
			Consumed:        false,
			Route:           []string{principal.Site},
			Approvals:       []Approval{},
			Controls:        []Control{},
		}
	case "approve":
		if session, ok := sessions[event.Session]; ok {
			session.Approvals = append(session.Approvals, Approval{
				EventID:   event.ID,
				Role:      event.Role,
				Principal: event.Principal,
				Time:      event.Time,
			})
		}
	case "control":
		if session, ok := sessions[event.Session]; ok {
			session.Controls = append(session.Controls, Control{
				EventID:   event.ID,
				Control:   event.Control,
				Principal: event.Principal,
				Time:      event.Time,
			})
		}
	case "hop":
		if session, ok := sessions[event.Session]; ok {
			session.Route = append(session.Route, event.ToZone)
			session.CurrentZone = event.ToZone
			session.HopCount++
		}
	case "lock":
		if _, ok := gateways[event.Gateway]; ok {
			gatewayLocked[event.Gateway] = true
		}
	case "unlock":
		if _, ok := gateways[event.Gateway]; ok {
			gatewayLocked[event.Gateway] = false
		}
	case "close":
		if session, ok := sessions[event.Session]; ok {
			session.State = "closed"
		}
	}
	_ = req
}

func buildDecision(req Case, principals map[string]Principal, resources map[string]Resource, sessions map[string]*SessionState, event Event, finding EventFinding) Decision {
	reasons := map[string]bool{}
	if finding.Status == "ignored" {
		reasons["event_ignored"] = true
	}

	session, ok := sessions[event.Session]
	if !ok {
		return Decision{
			ID:        event.ID,
			Session:   event.Session,
			Resource:  event.Resource,
			Status:    "deny",
			RiskScore: 0,
			Reasons:   orderedReasons(reasons, decisionReasonOrder),
			Approvals: []ProviderRow{},
			Controls:  []ProviderRow{},
			Route:     []string{},
		}
	}

	resource := resources[session.Resource]
	usableApprovals := make([]Approval, 0, len(session.Approvals))
	for _, approval := range session.Approvals {
		principal := principals[approval.Principal]
		if event.Time-approval.Time <= req.Policy.ApprovalWindow && principalValidAt(principal, event.Time) {
			usableApprovals = append(usableApprovals, approval)
		}
	}
	usableControls := make([]Control, 0, len(session.Controls))
	for _, control := range session.Controls {
		if event.Time-control.Time <= req.Policy.ControlWindow {
			usableControls = append(usableControls, control)
		}
	}

	approvalRows, roleProviders := approvalProviderRows(resource, usableApprovals)
	controlRows, controlProviders := controlProviderRows(resource, usableControls)

	if session.Consumed {
		reasons["token_replayed"] = true
	}
	if session.CurrentZone != resource.Zone {
		reasons["route_incomplete"] = true
	}
	for _, role := range resource.RequiredRoles {
		if len(roleProviders[role]) == 0 {
			reasons["missing_quorum"] = true
			break
		}
	}

	orgs := map[string]bool{}
	sites := map[string]bool{}
	rolePrincipals := map[string]map[string]bool{}
	roleOrgs := map[string]map[string]bool{}
	for _, role := range resource.RequiredRoles {
		rolePrincipals[role] = map[string]bool{}
		roleOrgs[role] = map[string]bool{}
	}
	externalApprovers := map[string]bool{}
	for _, approval := range usableApprovals {
		principal := principals[approval.Principal]
		orgs[principal.Org] = true
		sites[principal.Site] = true
		if contains(resource.RequiredRoles, approval.Role) {
			rolePrincipals[approval.Role][approval.Principal] = true
			roleOrgs[approval.Role][principal.Org] = true
		}
		if principal.External {
			externalApprovers[approval.Principal] = true
		}
	}
	if len(orgs) < resource.MinDistinctOrgs {
		reasons["org_diversity"] = true
	}
	if len(sites) < resource.MinDistinctSites {
		reasons["site_diversity"] = true
	}
	if separationViolation(resource, rolePrincipals, roleOrgs) {
		reasons["separation_violation"] = true
	}
	for _, control := range resource.RequiredControls {
		if len(controlProviders[control]) == 0 {
			reasons["missing_control"] = true
			break
		}
	}

	risk := riskScore(req, resource, session, event, externalApprovers)
	if risk > req.Policy.DenyAbove {
		reasons["risk_too_high"] = true
	}

	ordered := orderedReasons(reasons, decisionReasonOrder)
	status := "allow"
	if len(ordered) > 0 {
		status = "deny"
	} else if risk > req.Policy.StepUpAfter {
		status = "step_up"
	}

	return Decision{
		ID:        event.ID,
		Session:   event.Session,
		Resource:  session.Resource,
		Status:    status,
		RiskScore: risk,
		Reasons:   ordered,
		Approvals: approvalRows,
		Controls:  controlRows,
		Route:     append([]string(nil), session.Route...),
	}
}

func approvalProviderRows(resource Resource, approvals []Approval) ([]ProviderRow, map[string][]string) {
	providers := map[string][]string{}
	for _, approval := range approvals {
		if contains(resource.RequiredRoles, approval.Role) {
			providers[approval.Role] = append(providers[approval.Role], approval.EventID+":"+approval.Principal)
		}
	}
	rows := make([]ProviderRow, 0, len(resource.RequiredRoles))
	for _, role := range resource.RequiredRoles {
		rows = append(rows, ProviderRow{Role: role, Providers: uniqueSorted(providers[role])})
	}
	return rows, providers
}

func controlProviderRows(resource Resource, controls []Control) ([]ProviderRow, map[string][]string) {
	providers := map[string][]string{}
	for _, control := range controls {
		if contains(resource.RequiredControls, control.Control) {
			providers[control.Control] = append(providers[control.Control], control.EventID+":"+control.Principal)
		}
	}
	rows := make([]ProviderRow, 0, len(resource.RequiredControls))
	for _, control := range resource.RequiredControls {
		rows = append(rows, ProviderRow{Control: control, Providers: uniqueSorted(providers[control])})
	}
	return rows, providers
}

func separationViolation(resource Resource, rolePrincipals map[string]map[string]bool, roleOrgs map[string]map[string]bool) bool {
	for _, pair := range resource.SeparationPairs {
		if len(pair) != 2 {
			continue
		}
		for principal := range rolePrincipals[pair[0]] {
			if rolePrincipals[pair[1]][principal] {
				return true
			}
		}
	}
	for _, pair := range resource.OrgSeparationPairs {
		if len(pair) != 2 {
			continue
		}
		for org := range roleOrgs[pair[0]] {
			if roleOrgs[pair[1]][org] {
				return true
			}
		}
	}
	return false
}

func riskScore(req Case, resource Resource, session *SessionState, event Event, externalApprovers map[string]bool) int {
	risk := resource.BaseRisk
	for _, signal := range uniqueSorted(event.RiskSignals) {
		risk += req.Policy.RiskSignalScores[signal]
	}
	risk += 6 * len(externalApprovers)
	if 2*(event.Time-session.OpenTime) > (session.ExpiresAt - session.OpenTime) {
		risk += 4
	}
	if session.HopCount == req.Policy.MaxRouteHops {
		risk += 3
	}
	return risk
}

func signatureOK(secret string, event Event) bool {
	mac := hmac.New(sha256.New, []byte(secret))
	mac.Write([]byte(transcript(event)))
	expected := hex.EncodeToString(mac.Sum(nil))
	return hmac.Equal([]byte(expected), []byte(event.Signature))
}

func transcript(event Event) string {
	fields := []string{
		event.ID,
		fmt.Sprintf("%d", event.Revision),
		event.Type,
		event.Session,
		event.Principal,
		event.Resource,
		event.Role,
		event.Control,
		event.Gateway,
		event.FromZone,
		event.ToZone,
		event.Token,
		event.Challenge,
		fmt.Sprintf("%d", event.Time),
		fmt.Sprintf("%d", event.ExpiresAt),
		strings.Join(uniqueSorted(event.RiskSignals), ","),
	}
	return strings.Join(fields, "\n")
}

func clearanceOK(policy Policy, actual, minimum string) bool {
	rank := map[string]int{}
	for index, clearance := range policy.ClearanceOrder {
		rank[clearance] = index
	}
	actualRank, okActual := rank[actual]
	minRank, okMinimum := rank[minimum]
	if !okActual || !okMinimum {
		return false
	}
	return actualRank <= minRank
}

func principalValidAt(principal Principal, at int) bool {
	return principal.Available &&
		at >= principal.ActiveFrom &&
		at <= principal.ActiveUntil &&
		(principal.RevokedAfter == 0 || at < principal.RevokedAfter)
}

func orderedReasons(reasons map[string]bool, order []string) []string {
	out := []string{}
	for _, reason := range order {
		if reasons[reason] {
			out = append(out, reason)
		}
	}
	return out
}

func contains(values []string, wanted string) bool {
	for _, value := range values {
		if value == wanted {
			return true
		}
	}
	return false
}

func uniqueSorted(values []string) []string {
	seen := map[string]bool{}
	for _, value := range values {
		seen[value] = true
	}
	out := make([]string, 0, len(seen))
	for value := range seen {
		out = append(out, value)
	}
	sort.Strings(out)
	return out
}
