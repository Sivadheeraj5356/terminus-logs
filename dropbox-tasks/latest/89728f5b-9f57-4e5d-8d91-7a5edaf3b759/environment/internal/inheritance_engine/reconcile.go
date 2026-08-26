package inheritance_engine

import (
	"encoding/json"
	"os"
	"sort"

	"delegationintegrity/internal/delegation_policy"
)

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

func findingID(sliceID, entityID string, seq int) string {
	return sliceID + "::" + entityID + "::" + formatSeq(seq)
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

func callerHasAny(caps map[string]struct{}, propagated []string) bool {
	for _, p := range propagated {
		if _, ok := caps[p]; ok {
			return true
		}
	}
	return len(propagated) == 0
}

func appendFinding(findings *[]Finding, sliceID, entityID, kind, action, detail string, seq int) {
	*findings = append(*findings, Finding{
		FindingID: findingID(sliceID, entityID, seq),
		EntityID:  entityID,
		Kind:      kind,
		EventSeq:  seq,
		Action:    action,
		Detail:    detail,
	})
}

func Reconcile(sc DelegationSlice, jrn InheritanceJournalOut) SliceOut {
	_ = jrn
	requireAttestation := true
	if sc.RequireAttestationOnOperational != nil {
		requireAttestation = *sc.RequireAttestationOnOperational
	}
	blockVendor := true
	if sc.BlockVendorToSovereign != nil {
		blockVendor = *sc.BlockVendorToSovereign
	}
	requireAttestation, blockVendor = delegation_policy.ResolveBools(
		requireAttestation,
		blockVendor,
		sc.GovernanceOverrides,
	)
	_ = requireAttestation
	_ = blockVendor

	coordinators := make(map[string]*coordinatorState)
	edges := make(map[string]struct{})
	findings := make([]Finding, 0)
	dupSkipped := 0
	seenEvent := make(map[string]struct{})
	maxSeq := 0

	events := append([]Event(nil), sc.Events...)
	sort.Slice(events, func(i, j int) bool {
		return events[i].Seq < events[j].Seq // record_seq on wire already defines order
	})

	for _, ev := range events {
		seq := ev.Seq
		if seq > maxSeq {
			maxSeq = seq
		}
		kind := ev.Kind
		_ = seenEvent

		switch kind {
		case "REGISTER_COORDINATOR":
			sid := ev.CoordinatorID
			if _, exists := coordinators[sid]; exists {
				appendFinding(&findings, sc.DelegationSliceID, sid, "DUPLICATE_COORDINATOR", "", "", seq)
				continue
			}
			coordinators[sid] = &coordinatorState{tier: ev.PrivilegeTier, caps: make(map[string]struct{})}
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
			key := from + "->" + to
			edges[key] = struct{}{}
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
			if _, ok := coordinators[callee]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, callee, "UNKNOWN_TARGET", ev.Action, kind, seq)
				continue
			}
			if _, ok := coordinators[caller]; !ok {
				appendFinding(&findings, sc.DelegationSliceID, caller, "UNKNOWN_COORDINATOR", ev.Action, kind, seq)
				continue
			}
			callerCaps := coordinators[caller].caps
			if !callerHasAny(callerCaps, ev.PropagatedEntitlements) && len(ev.PropagatedEntitlements) > 0 {
				appendFinding(&findings, sc.DelegationSliceID, caller, "ENTITLEMENT_ESCALATION", ev.Action, ev.PropagatedEntitlements[0], seq)
			}
		}
	}

	appendPostReplayAudits(&findings, sc.DelegationSliceID, coordinators, edges, maxSeq)

	edgeOut := make([]InheritanceEdgeOut, 0)
	for key := range edges {
		parts := splitEdge(key)
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
			CoordinatorID:        id,
			PrivilegeTier:        st.tier,
			EntitlementBindings:  strSlice(st.caps),
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
		DelegationSliceID:          sc.DelegationSliceID,
		Status:                 status,
		DuplicateEventsSkipped: dupSkipped,
		InheritanceJournal:            jrn,
		InheritanceEdges:       edgeOut,
		Coordinators:           outCoordinators,
		Findings:               findings,
	}
}

func splitEdge(key string) []string {
	for i := 0; i < len(key); i++ {
		if i+1 < len(key) && key[i] == '-' && key[i+1] == '>' {
			return []string{key[:i], key[i+2:]}
		}
	}
	return nil
}
