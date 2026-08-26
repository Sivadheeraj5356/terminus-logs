package driver

import (
	"missiondesk/lib/judge"
	"missiondesk/lib/intake"
	"missiondesk/lib/cstore"
	"missiondesk/lib/ix"
	"missiondesk/lib/model"
)

func Assess(rec model.Record, pol model.Policy, sf cstore.StateFile) (model.Assessment, error) {
	if err := judge.RequirePublishable(rec.EmergencyAuthority); err != nil {
		return model.Assessment{}, err
	}
	axis := map[string]int{}
	for _, item := range rec.Evidence {
		axis[item.Axis] += intake.Contribution(item)
	}
	critical, major := judge.CountDissent(rec.Evidence)
	prior := cstore.StateFor(sf, rec.CaseID)
	open, closed, overdueOpen := cstore.Reconcile(rec, prior, pol)
	stagnation := ix.StagnationPenalty(prior, open)
	st := prior
	st.CaseID = rec.CaseID
	st.Runs++
	st.OpenCommitments = open
	st.ClosedCommitments = closed
	delegated := judge.DelegatedFlag(rec.EmergencyAuthority)
	idx, label, err := ix.Resilience(axis, critical, major, delegated, stagnation)
	if err != nil {
		return model.Assessment{}, err
	}
	decision := judge.Choose(axis, pol, rec.EmergencyAuthority, critical, major, open, overdueOpen)
	st.LastDecision = decision
	cstore.PutState(sf, st)
	return model.Assessment{
		CaseID:                 rec.CaseID,
		TechnicalCertification: rec.TechnicalCertification,
		EmergencyStatus:        rec.EmergencyAuthority.Status,
		Decision:               decision,
		AxisScores:             axis,
		UnresolvedCritical:     critical,
		UnresolvedMajor:        major,
		OpenCommitmentIDs:      cstore.CommitmentIDs(open),
		ClosedCommitmentIDs:    cstore.CommitmentIDs(closed),
		ResilienceIndex:        idx,
		ResilienceLabel:        label,
		StagnationPenalty:      stagnation,
		OverdueOpen:            overdueOpen,
		Evidence:               rec.Evidence,
		State:                  st,
		AlternativesRejected:   judge.Alternatives(decision),
	}, nil
}
