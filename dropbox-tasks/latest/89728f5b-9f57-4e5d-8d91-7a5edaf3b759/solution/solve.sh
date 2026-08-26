#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/internal/elwjwire/decode.go <<'DECODE_EOF'
package elwjwire

import (
	"encoding/binary"
	"encoding/json"
	"errors"
	"hash/crc32"
	"os"

	"delegationintegrity/internal/inheritance_engine"
)

type Stats struct {
	FormatVersion   int `json:"format_version"`
	RecordsTotal    int `json:"records_total"`
	RecordsValid    int `json:"records_valid"`
	RecordsRejected int `json:"records_rejected"`
	DupSeqRejects   int `json:"dup_seq_rejects"`
	TruncatedTail   int `json:"truncated_tail"`
	PayloadBytes    int `json:"payload_bytes"`
}

func Decode(path string) ([]inheritance_engine.Event, Stats, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, Stats{}, err
	}
	if len(data) < 8 || string(data[:4]) != "ELWJ" {
		return nil, Stats{}, errors.New("bad magic")
	}
	formatVersion := int(binary.LittleEndian.Uint32(data[4:8]))
	stats := Stats{FormatVersion: formatVersion}
	if formatVersion != 1 {
		return nil, stats, errors.New("unsupported format_version")
	}
	off := 8
	seen := make(map[uint32]struct{})
	events := make([]inheritance_engine.Event, 0)
	for off < len(data) {
		if off+12 > len(data) {
			stats.RecordsRejected++
			stats.TruncatedTail = 1
			break
		}
		recordSeq := binary.LittleEndian.Uint32(data[off : off+4])
		flags := binary.LittleEndian.Uint16(data[off+4 : off+6])
		reserved := binary.LittleEndian.Uint16(data[off+6 : off+8])
		payloadLen := binary.LittleEndian.Uint32(data[off+8 : off+12])
		off += 12
		stats.RecordsTotal++
		reason := ""
		if reserved != 0 {
			reason = "BAD_RESERVED"
		} else if flags != 0 {
			reason = "BAD_FLAGS"
		} else if payloadLen > 5120 {
			reason = "LEN_OVERFLOW"
		} else if _, ok := seen[recordSeq]; ok {
			reason = "DUP_SEQ"
		}
		if reason == "LEN_OVERFLOW" {
			if off+int(payloadLen)+4 <= len(data) {
				off += int(payloadLen) + 4
				stats.RecordsRejected++
				seen[recordSeq] = struct{}{}
				continue
			}
			stats.RecordsRejected++
			stats.TruncatedTail = 1
			break
		}
		if off+int(payloadLen)+4 > len(data) {
			stats.RecordsRejected++
			stats.TruncatedTail = 1
			break
		}
		payload := data[off : off+int(payloadLen)]
		off += int(payloadLen)
		checksum := binary.LittleEndian.Uint32(data[off : off+4])
		off += 4
		if reason == "" {
			hdr := make([]byte, 12)
			binary.LittleEndian.PutUint32(hdr[0:4], recordSeq)
			binary.LittleEndian.PutUint16(hdr[4:6], flags)
			binary.LittleEndian.PutUint16(hdr[6:8], reserved)
			binary.LittleEndian.PutUint32(hdr[8:12], payloadLen)
			if crc32.ChecksumIEEE(append(hdr, payload...)) != checksum {
				reason = "BAD_CRC"
			}
		}
		seen[recordSeq] = struct{}{}
		if reason != "" {
			stats.RecordsRejected++
			if reason == "DUP_SEQ" {
				stats.DupSeqRejects++
			}
			continue
		}
		var ev inheritance_engine.Event
		if err := json.Unmarshal(payload, &ev); err != nil {
			stats.RecordsRejected++
			continue
		}
		stats.RecordsValid++
		stats.PayloadBytes += int(payloadLen)
		events = append(events, ev)
	}
	return events, stats, nil
}
DECODE_EOF

cat > /app/internal/inheritance_engine/reconcile.go <<'REPLAY_EOF'
package inheritance_engine

import (
	"encoding/json"
	"os"
	"sort"
	"strings"

	"delegationintegrity/internal/delegation_policy"
)

type Event struct {
	Seq                    int      `json:"seq"`
	EventID                string   `json:"event_id"`
	CoordinatorID              string   `json:"coordinator_id"`
	Kind                   string   `json:"kind"`
	PrivilegeTier   string   `json:"privilege_tier"`
	BusinessUnit         string   `json:"business_unit"`
	GrantorCoordinator    string   `json:"grantor_coordinator"`
	GranteeCoordinator              string   `json:"grantee_coordinator"`
	EntitlementKey             string   `json:"entitlement_key"`
	RequestorID               string   `json:"requestor_id"`
	EvalTargetID               string   `json:"eval_target_id"`
	Action                 string   `json:"action"`
	HasGovernanceAttestation               bool     `json:"has_governance_attestation"`
	PropagatedEntitlements  []string `json:"propagated_entitlements"`
	ProvenanceRequestor         string   `json:"provenance_requestor"`
}

type DelegationSlice struct {
	DelegationSliceID               string                 `json:"delegation_slice_id"`
	RequireAttestationOnOperational   *bool                  `json:"require_attestation_on_operational"`
	BlockVendorToSovereign *bool                  `json:"block_vendor_to_sovereign"`
	GovernanceOverrides          map[string]interface{} `json:"governance_overrides"`
	Events                   []Event                `json:"events"`
}

type InheritanceEdgeOut struct {
	GrantorCoordinator string `json:"grantor_coordinator"`
	GranteeCoordinator   string `json:"grantee_coordinator"`
}

type CoordinatorOut struct {
	CoordinatorID         string   `json:"coordinator_id"`
	PrivilegeTier              string   `json:"privilege_tier"`
	EntitlementBindings      []string `json:"entitlement_bindings"`
	DelegationPoisonRisk string   `json:"delegation_poison_risk"`
}

type InheritanceJournalOut struct {
	FormatVersion   int `json:"format_version"`
	RecordsTotal    int `json:"records_total"`
	RecordsValid    int `json:"records_valid"`
	RecordsRejected int `json:"records_rejected"`
	DupSeqRejects   int `json:"dup_seq_rejects"`
	TruncatedTail   int `json:"truncated_tail"`
	PayloadBytes    int `json:"payload_bytes"`
}

type Finding struct {
	FindingID string `json:"finding_id"`
	EntityID  string `json:"entity_id"`
	Kind      string `json:"kind"`
	EventSeq  int    `json:"event_seq"`
	Action    string `json:"action"`
	Detail    string `json:"detail"`
}

type SliceOut struct {
	DelegationSliceID             string       `json:"delegation_slice_id"`
	Status                 string       `json:"status"`
	DuplicateEventsSkipped int          `json:"duplicate_events_skipped"`
	InheritanceJournal                InheritanceJournalOut   `json:"inheritance_journal"`
	InheritanceEdges         []InheritanceEdgeOut    `json:"inheritance_edges"`
	Coordinators               []CoordinatorOut `json:"coordinators"`
	Findings               []Finding    `json:"findings"`
}

type Report struct {
	DelegationSlices []SliceOut `json:"delegation_slices"`
}

type coordinatorState struct {
	tier   string
	tenant string
	caps   map[string]struct{}
}

func LoadDelegationSlice(path string) (DelegationSlice, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return DelegationSlice{}, err
	}
	var sc DelegationSlice
	if err := json.Unmarshal(data, &sc); err != nil {
		return DelegationSlice{}, err
	}
	return sc, nil
}

func findingID(scenarioID, entityID string, seq int) string {
	return scenarioID + "::" + entityID + "::" + formatSeq(seq)
}

func formatSeq(seq int) string {
	if seq < 0 {
		seq = 0
	}
	s := []byte("0000")
	n := seq
	for i := 3; i >= 0; i-- {
		s[i] = byte('0' + n%10)
		n /= 10
	}
	return string(s)
}

func strSlice(m map[string]struct{}) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	sort.Strings(out)
	return out
}

func delegationPoisonRisk(tier string) string {
	switch tier {
	case "vendor":
		return "elevated"
	case "sovereign":
		return "critical"
	default:
		return "contained"
	}
}

func edgeKey(from, to string) string {
	return from + "\x00" + to
}

func hasEdge(edges map[string]struct{}, from, to string) bool {
	_, ok := edges[edgeKey(from, to)]
	return ok
}

func appendFinding(findings *[]Finding, scenarioID, entityID, kind, action, detail string, seq int) {
	*findings = append(*findings, Finding{
		FindingID: findingID(scenarioID, entityID, seq),
		EntityID:  entityID,
		Kind:      kind,
		EventSeq:  seq,
		Action:    action,
		Detail:    detail,
	})
}

func firstMissingProp(caps map[string]struct{}, propagated []string) string {
	missing := make([]string, 0)
	for _, p := range propagated {
		if p == "" {
			continue
		}
		if _, ok := caps[p]; !ok {
			missing = append(missing, p)
		}
	}
	sort.Strings(missing)
	if len(missing) == 0 {
		return ""
	}
	return missing[0]
}

func resolveBusinessUnit(raw string) string {
	s := strings.ToLower(strings.TrimSpace(raw))
	s = strings.ReplaceAll(s, "_", "-")
	if s == "" {
		return "business-core"
	}
	return s
}

func removeEdgesFor(edges map[string]struct{}, pid string) {
	for key := range edges {
		parts := splitEdgeKey(key)
		if len(parts) == 2 && (parts[0] == pid || parts[1] == pid) {
			delete(edges, key)
		}
	}
}

func Reconcile(sc DelegationSlice, cap InheritanceJournalOut) SliceOut {
	requireTokenValidation := true
	if sc.RequireAttestationOnOperational != nil {
		requireTokenValidation = *sc.RequireAttestationOnOperational
	}
	blockPartner := true
	if sc.BlockVendorToSovereign != nil {
		blockPartner = *sc.BlockVendorToSovereign
	}
	requireTokenValidation, blockPartner = delegation_policy.ResolveBools(
		requireTokenValidation,
		blockPartner,
		sc.GovernanceOverrides,
	)

	coordinators := make(map[string]*coordinatorState)
	tombstones := make(map[string]struct{})
	edges := make(map[string]struct{})
	findings := make([]Finding, 0)
	dupSkipped := 0
	seenEvent := make(map[string]struct{})
	entEscFlagged := make(map[string]struct{})
	maxSeq := 0

	events := append([]Event(nil), sc.Events...)
	sort.Slice(events, func(i, j int) bool {
		if events[i].Seq != events[j].Seq {
			return events[i].Seq < events[j].Seq
		}
		if events[i].CoordinatorID != events[j].CoordinatorID {
			return events[i].CoordinatorID < events[j].CoordinatorID
		}
		return events[i].EventID < events[j].EventID
	})

	for _, ev := range events {
		seq := ev.Seq
		if seq > maxSeq {
			maxSeq = seq
		}
		kind := ev.Kind
		idKey := strings.TrimSpace(ev.EventID)
		if idKey != "" {
			if _, dup := seenEvent[idKey]; dup {
				dupSkipped++
				continue
			}
			seenEvent[idKey] = struct{}{}
		}

		switch kind {
		case "REGISTER_COORDINATOR":
			sid := ev.CoordinatorID
			if _, purged := tombstones[sid]; purged {
				appendFinding(&findings, sc.DelegationSliceID, sid, "RESURRECTED_ENTITLEMENT", "", "", seq)
				continue
			}
			if _, exists := coordinators[sid]; exists {
				appendFinding(&findings, sc.DelegationSliceID, sid, "DUPLICATE_COORDINATOR", "", "", seq)
				continue
			}
			coordinators[sid] = &coordinatorState{
				tier:   ev.PrivilegeTier,
				tenant: resolveBusinessUnit(ev.BusinessUnit),
				caps:   make(map[string]struct{}),
			}
		case "RETIRE_COORDINATOR_SCOPE":
			sid := ev.CoordinatorID
			if _, ok := coordinators[sid]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, sid, "UNKNOWN_COORDINATOR", "", kind, seq)
				continue
			}
			delete(coordinators, sid)
			tombstones[sid] = struct{}{}
			removeEdgesFor(edges, sid)
		case "GRANT_INHERITANCE":
			from := ev.GrantorCoordinator
			to := ev.GranteeCoordinator
			if _, ok := coordinators[from]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, from, "UNKNOWN_COORDINATOR", "", kind, seq)
				continue
			}
			if _, ok := coordinators[to]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, to, "UNKNOWN_TARGET", "", kind, seq)
				continue
			}
			key := edgeKey(from, to)
			if _, exists := edges[key]; exists {
				appendFinding(&findings, sc.DelegationSliceID, to, "DUPLICATE_INHERITANCE", "", from, seq)
				continue
			}
			edges[key] = struct{}{}
		case "REVOKE_INHERITANCE":
			from := ev.GrantorCoordinator
			to := ev.GranteeCoordinator
			if _, ok := coordinators[from]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, from, "UNKNOWN_COORDINATOR", "", kind, seq)
				continue
			}
			if _, ok := coordinators[to]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, to, "UNKNOWN_TARGET", "", kind, seq)
				continue
			}
			delete(edges, edgeKey(from, to))
		case "BIND_ENTITLEMENT":
			sid := ev.CoordinatorID
			if _, ok := coordinators[sid]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, sid, "UNKNOWN_COORDINATOR", "", kind, seq)
				continue
			}
			coordinators[sid].caps[ev.EntitlementKey] = struct{}{}
		case "ACCESS_EVAL":
			caller := ev.RequestorID
			callee := ev.EvalTargetID
			action := ev.Action
			calleeSt, ok := coordinators[callee]
			if !ok {
				appendFinding(&findings, sc.DelegationSliceID, callee, "UNKNOWN_TARGET", action, kind, seq)
				continue
			}
			callerSt, ok := coordinators[caller]
			if !ok {
				appendFinding(&findings, sc.DelegationSliceID, caller, "UNKNOWN_COORDINATOR", action, kind, seq)
				continue
			}
			if !hasEdge(edges, caller, callee) {
				appendFinding(&findings, sc.DelegationSliceID, callee, "UNTRUSTED_INHERITANCE", action, caller, seq)
				continue
			}
			if callerSt.tenant != calleeSt.tenant {
				appendFinding(&findings, sc.DelegationSliceID, callee, "DOMAIN_BLEED", action, caller, seq)
				continue
			}
			if callerSt.tier == "vendor" && calleeSt.tier == "sovereign" {
				_, hasAudit := calleeSt.caps["governance:audit"]
				if blockPartner || !hasAudit {
					appendFinding(&findings, sc.DelegationSliceID, caller, "RESTRICTED_TIER", action, callee, seq)
					continue
				}
			}
			if requireTokenValidation && calleeSt.tier == "operational" && !ev.HasGovernanceAttestation {
				appendFinding(&findings, sc.DelegationSliceID, callee, "UNATTESTED_ACCESS", action, "", seq)
				continue
			}
			if miss := firstMissingProp(callerSt.caps, ev.PropagatedEntitlements); miss != "" {
				pkey := caller + "::" + miss
				if _, done := entEscFlagged[pkey]; !done {
					entEscFlagged[pkey] = struct{}{}
					appendFinding(&findings, sc.DelegationSliceID, caller, "ENTITLEMENT_ESCALATION", action, miss, seq)
				}
			}
			orig := ev.ProvenanceRequestor
			if orig != "" && orig != caller {
				if miss := firstMissingProp(callerSt.caps, ev.PropagatedEntitlements); miss != "" {
					appendFinding(&findings, sc.DelegationSliceID, orig, "LATERAL_GHOSTING", action, miss, seq)
				}
			}
		}
	}

	auditSeq := maxSeq + 1
	meshFlagged := make(map[string]struct{})
	openFlagged := make(map[string]struct{})

	for key := range edges {
		parts := splitEdgeKey(key)
		if len(parts) != 2 {
			continue
		}
		from, to := parts[0], parts[1]
		fromSt, ok1 := coordinators[from]
		toSt, ok2 := coordinators[to]
		if !ok1 || !ok2 {
			continue
		}
		if fromSt.tier == "vendor" && toSt.tier == "operational" {
			mkey := from + "::" + to
			if _, done := meshFlagged[mkey]; done {
				continue
			}
			if !hasEdge(edges, to, from) {
				meshFlagged[mkey] = struct{}{}
				appendFinding(&findings, sc.DelegationSliceID, to, "INHERITANCE_ASYMMETRY", "", from, auditSeq)
			}
		}
	}

	for sid, st := range coordinators {
		if st.tier != "sovereign" {
			continue
		}
		if _, ok := st.caps["governance:audit"]; ok {
			continue
		}
		partners := make([]string, 0)
		for key := range edges {
			parts := splitEdgeKey(key)
			if len(parts) != 2 {
				continue
			}
			from, to := parts[0], parts[1]
			if to != sid {
				continue
			}
			if fs, ok := coordinators[from]; ok && fs.tier == "vendor" {
				partners = append(partners, from)
			}
		}
		if len(partners) == 0 {
			continue
		}
		sort.Strings(partners)
		if _, done := openFlagged[sid]; !done {
			openFlagged[sid] = struct{}{}
			appendFinding(&findings, sc.DelegationSliceID, sid, "OPEN_GHOST_PATH", "", partners[0], auditSeq)
		}
	}

	for sid, st := range coordinators {
		if st.tier == "sovereign" {
			if _, ok := st.caps["governance:admin"]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, sid, "SOVEREIGN_UNBOUND", "", "", auditSeq)
			}
		}
	}

	edgeOut := make([]InheritanceEdgeOut, 0, len(edges))
	for key := range edges {
		parts := splitEdgeKey(key)
		if len(parts) == 2 {
			edgeOut = append(edgeOut, InheritanceEdgeOut{GrantorCoordinator: parts[0], GranteeCoordinator: parts[1]})
		}
	}
	sort.Slice(edgeOut, func(i, j int) bool {
		if edgeOut[i].GrantorCoordinator != edgeOut[j].GrantorCoordinator {
			return edgeOut[i].GrantorCoordinator < edgeOut[j].GrantorCoordinator
		}
		return edgeOut[i].GranteeCoordinator < edgeOut[j].GranteeCoordinator
	})

	outCoordinators := make([]CoordinatorOut, 0, len(coordinators))
	sids := make([]string, 0, len(coordinators))
	for id := range coordinators {
		sids = append(sids, id)
	}
	sort.Strings(sids)
	for _, id := range sids {
		st := coordinators[id]
		outCoordinators = append(outCoordinators, CoordinatorOut{
			CoordinatorID:         id,
			PrivilegeTier:              st.tier,
			EntitlementBindings:      strSlice(st.caps),
			DelegationPoisonRisk: delegationPoisonRisk(st.tier),
		})
	}

	sort.Slice(findings, func(i, j int) bool {
		return findings[i].FindingID < findings[j].FindingID
	})

	status := "VALID"
	if len(findings) > 0 {
		status = "INVALID"
	}

	return SliceOut{
		DelegationSliceID:             sc.DelegationSliceID,
		Status:                 status,
		DuplicateEventsSkipped: dupSkipped,
		InheritanceJournal:                cap,
		InheritanceEdges:         edgeOut,
		Coordinators:               outCoordinators,
		Findings:               findings,
	}
}

func splitEdgeKey(key string) []string {
	for i := 0; i < len(key); i++ {
		if key[i] == 0 {
			return []string{key[:i], key[i+1:]}
		}
	}
	return nil
}
REPLAY_EOF

cat > /app/internal/elwjwire/wire.go <<'WIRE_EOF'
package elwjwire

import "encoding/binary"

func readRecordHeader(buf []byte) (recordSeq uint32, flags, reserved uint16, payloadLen uint32) {
	recordSeq = binary.LittleEndian.Uint32(buf[0:4])
	flags = binary.LittleEndian.Uint16(buf[4:6])
	reserved = binary.LittleEndian.Uint16(buf[6:8])
	payloadLen = binary.LittleEndian.Uint32(buf[8:12])
	return recordSeq, flags, reserved, payloadLen
}

func checksumHeaderLE(recordSeq uint32, flags, reserved uint16, payloadLen uint32) []byte {
	hdr := make([]byte, 12)
	binary.LittleEndian.PutUint32(hdr[0:4], recordSeq)
	binary.LittleEndian.PutUint16(hdr[4:6], flags)
	binary.LittleEndian.PutUint16(hdr[6:8], reserved)
	binary.LittleEndian.PutUint32(hdr[8:12], payloadLen)
	return hdr
}
WIRE_EOF

cat > /app/internal/delegation_policy/policy.go <<'POLICY_EOF'
package delegation_policy

func ResolveBools(requireAttestation, blockVendor bool, overrides map[string]interface{}) (bool, bool) {
	if overrides == nil {
		return requireAttestation, blockVendor
	}
	if v, ok := overrides["require_attestation_on_operational"]; ok {
		if b, ok := toBool(v); ok {
			requireAttestation = b
		}
	}
	if v, ok := overrides["block_vendor_to_sovereign"]; ok {
		if b, ok := toBool(v); ok {
			blockVendor = b
		}
	}
	return requireAttestation, blockVendor
}

func toBool(v interface{}) (bool, bool) {
	switch x := v.(type) {
	case bool:
		return x, true
	default:
		return false, false
	}
}
POLICY_EOF

cat > /app/cmd/delegationintegrity/main.go <<'MAIN_EOF'
package main

import (
	"encoding/json"
	"fmt"
	"os"

	"delegationintegrity/internal/elwjwire"
	"delegationintegrity/internal/inheritance_engine"
)

type reconcileCatalog struct {
	DelegationSlices []string `json:"delegation_slices"`
}

func main() {
	fixtureRoot := "/app/delegation_federation_slices"
	catalogPath := fixtureRoot + "/federation_slice_roll.json"
	outPath := "/app/build/delegation_integrity_snapshot.json"

	raw, err := os.ReadFile(catalogPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "read catalog: %v\n", err)
		os.Exit(1)
	}
	var catalog reconcileCatalog
	if err := json.Unmarshal(raw, &catalog); err != nil {
		fmt.Fprintf(os.Stderr, "parse catalog: %v\n", err)
		os.Exit(1)
	}

	report := inheritance_engine.Report{DelegationSlices: make([]inheritance_engine.SliceOut, 0, len(catalog.DelegationSlices))}
	for _, id := range catalog.DelegationSlices {
		cfgPath := fixtureRoot + "/" + id + ".json"
		wormPath := fixtureRoot + "/" + id + "/inheritance_journal.elwj"
		sl, err := inheritance_engine.LoadDelegationSlice(cfgPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "load %s: %v\n", cfgPath, err)
			os.Exit(1)
		}
		events, wormStats, err := elwjwire.Decode(wormPath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "decode %s: %v\n", wormPath, err)
			os.Exit(1)
		}
		sl.Events = events
		wormOut := inheritance_engine.InheritanceJournalOut{
			FormatVersion:   wormStats.FormatVersion,
			RecordsTotal:    wormStats.RecordsTotal,
			RecordsValid:    wormStats.RecordsValid,
			RecordsRejected: wormStats.RecordsRejected,
			DupSeqRejects:   wormStats.DupSeqRejects,
			TruncatedTail:   wormStats.TruncatedTail,
			PayloadBytes:    wormStats.PayloadBytes,
		}
		report.DelegationSlices = append(report.DelegationSlices, inheritance_engine.Reconcile(sl, wormOut))
	}

	if err := os.MkdirAll("/app/build", 0o755); err != nil {
		fmt.Fprintf(os.Stderr, "mkdir: %v\n", err)
		os.Exit(1)
	}
	enc, err := json.Marshal(report)
	if err != nil {
		fmt.Fprintf(os.Stderr, "marshal: %v\n", err)
		os.Exit(1)
	}
	out := append(enc, '\n')
	if err := os.WriteFile(outPath, out, 0o644); err != nil {
		fmt.Fprintf(os.Stderr, "write: %v\n", err)
		os.Exit(1)
	}
}
MAIN_EOF

rm -f /app/internal/inheritance_engine/types.go /app/internal/inheritance_engine/audits.go

make clean || true
make build
make run

test -s /app/build/delegation_integrity_snapshot.json
test -x /app/build/delegationintegrity
