package audit

import (
	"fmt"
	"sort"
	"strings"

	"backuptrust/schema"
)

// AssessArchive evaluates one backup archive against policy and returns findings.
func AssessArchive(a schema.ArchiveFile, p schema.Policy) schema.ArchiveResult {
	approved := setOf(p.Ciphers.Approved)
	staleCipher := setOf(p.Ciphers.Stale)
	staleAlgo := setOf(p.Algorithms.Stale)
	trusted := setOf(p.Restore.TrustedSigners)

	keys := map[string]schema.Key{}
	for _, k := range a.Keys {
		keys[k.ID] = k
	}
	signed := setOf(a.Manifest.SignedDigests)

	var gaps []schema.CoverageGap
	var muts []schema.UnauthorizedMutation
	var escrows []schema.EscrowBreak
	var weak []schema.RecoveryWeakness
	var ret []schema.RetentionTamper
	var guars []schema.RecoveryGuaranteeFail
	var stales []schema.StaleDependency
	var forges []schema.RestoreForgery
	var corrs []schema.SilentCorruption
	var resils []schema.ResilienceFail
	var findings []schema.Finding
	var evidence []schema.Evidence

	addFinding := func(kind, subject, detail string) {
		findings = append(findings, schema.Finding{Kind: kind, Subject: subject, Detail: detail})
		evidence = append(evidence, schema.Evidence{Kind: kind, Ref: subject})
	}

	for _, obj := range a.Objects {
		cipher := strings.TrimSpace(obj.Cipher)
		lower := strings.ToLower(cipher)
		if cipher == "" || lower == "none" || lower == "plaintext" || !approved[cipher] {
			reason := "not_approved"
			if cipher == "" || lower == "none" || lower == "plaintext" {
				reason = "unencrypted"
			}
			gaps = append(gaps, schema.CoverageGap{ObjectID: obj.ID, Cipher: cipher, Reason: reason})
			addFinding("coverage_gap", obj.ID, reason+":"+cipher)
		}
		if staleCipher[cipher] {
			stales = append(stales, schema.StaleDependency{Subject: obj.ID, Kind: "cipher", Value: cipher})
			addFinding("stale_dependency", obj.ID, "cipher:"+cipher)
		}

		reason := ""
		if obj.ContentDigest != obj.DeclaredDigest {
			reason = "digest_mismatch"
		} else if !signed[obj.ContentDigest] {
			reason = "unsigned_digest"
		}
		if reason != "" {
			muts = append(muts, schema.UnauthorizedMutation{
				ObjectID: obj.ID, ContentDigest: obj.ContentDigest, DeclaredDigest: obj.DeclaredDigest, Reason: reason,
			})
			addFinding("unauthorized_mutation", obj.ID, reason)
		}

		if k, ok := keys[obj.KeyID]; ok {
			if k.State == "revoked" || k.State == "destroyed" {
				guars = append(guars, schema.RecoveryGuaranteeFail{KeyID: k.ID, ObjectID: obj.ID, Reason: "key_" + k.State})
				addFinding("recovery_guarantee_fail", k.ID, obj.ID+":key_"+k.State)
			} else if k.RewrapNeeded && strings.TrimSpace(k.RewrapToken) == "" {
				guars = append(guars, schema.RecoveryGuaranteeFail{KeyID: k.ID, ObjectID: obj.ID, Reason: "missing_rewrap_token"})
				addFinding("recovery_guarantee_fail", k.ID, obj.ID+":missing_rewrap_token")
			}
		}
	}

	for _, k := range a.Keys {
		if staleAlgo[k.Algorithm] {
			stales = append(stales, schema.StaleDependency{Subject: k.ID, Kind: "algorithm", Value: k.Algorithm})
			addFinding("stale_dependency", k.ID, "algorithm:"+k.Algorithm)
		}
		if k.Role != "escrow" {
			continue
		}
		registered := setOf(a.Escrow.RegisteredFingerprints[k.ID])
		valid := 0
		for _, sh := range k.Shares {
			if sh.Revoked {
				continue
			}
			if registered[sh.Fingerprint] {
				valid++
			}
		}
		req := p.Escrow.MinQuorum
		if k.Threshold > req {
			req = k.Threshold
		}
		if valid < req {
			escrows = append(escrows, schema.EscrowBreak{
				KeyID: k.ID, ValidShares: valid, RequiredQuorum: req, Reason: "quorum_shortfall",
			})
			addFinding("escrow_break", k.ID, fmt.Sprintf("%d<%d", valid, req))
		}
	}

	if a.Recovery.PathCount < 2 && a.Recovery.RequiresOnlineHSM {
		if !(a.Recovery.OfflineColdShare || a.Recovery.GeographicSplit) {
			weak = append(weak, schema.RecoveryWeakness{Reason: "single_online_hsm_path"})
			addFinding("recovery_weakness", a.ArchiveID, "single_online_hsm_path")
		}
	}

	suppressRetention := a.Retention.LegalHold && a.Retention.EnforcedDays >= a.Retention.DeclaredDays
	if !suppressRetention {
		reason := ""
		if p.Retention.RequiresImmutable && !a.Retention.Immutable {
			reason = "mutable_store"
		} else if a.Retention.EnforcedDays < a.Retention.DeclaredDays {
			reason = "enforced_below_declared"
		}
		if reason != "" {
			ret = append(ret, schema.RetentionTamper{
				DeclaredDays: a.Retention.DeclaredDays,
				EnforcedDays: a.Retention.EnforcedDays,
				Reason:       reason,
			})
			addFinding("retention_tamper", a.ArchiveID, reason)
		}
	}

	if a.Restore.NonceReuse {
		forges = append(forges, schema.RestoreForgery{Signer: a.Restore.Signer, Reason: "nonce_reuse"})
		addFinding("restore_forgery", a.Restore.Signer, "nonce_reuse")
	} else if !a.Restore.ChainOK {
		forges = append(forges, schema.RestoreForgery{Signer: a.Restore.Signer, Reason: "chain_broken"})
		addFinding("restore_forgery", a.Restore.Signer, "chain_broken")
	} else if !trusted[a.Restore.Signer] {
		forges = append(forges, schema.RestoreForgery{Signer: a.Restore.Signer, Reason: "untrusted_signer"})
		addFinding("restore_forgery", a.Restore.Signer, "untrusted_signer")
	}

	if a.ExpectedShards != len(a.Shards) {
		corrs = append(corrs, schema.SilentCorruption{ShardID: a.ArchiveID, Reason: "shard_count_mismatch"})
		addFinding("silent_corruption", a.ArchiveID, "shard_count_mismatch")
	}
	for _, sh := range a.Shards {
		if sh.DeclaredCRC != sh.PayloadCRC {
			corrs = append(corrs, schema.SilentCorruption{ShardID: sh.ID, Reason: "crc_mismatch"})
			addFinding("silent_corruption", sh.ID, "crc_mismatch")
		}
	}

	for _, t := range a.AdversaryTests {
		if !t.Surviving {
			resils = append(resils, schema.ResilienceFail{TestID: t.ID, Reason: "adversary_surviving_false"})
			addFinding("resilience_fail", t.ID, "adversary_surviving_false")
		}
	}

	sort.Slice(gaps, func(i, j int) bool { return gaps[i].ObjectID < gaps[j].ObjectID })
	sort.Slice(muts, func(i, j int) bool { return muts[i].ObjectID < muts[j].ObjectID })
	sort.Slice(escrows, func(i, j int) bool { return escrows[i].KeyID < escrows[j].KeyID })
	sort.Slice(weak, func(i, j int) bool { return weak[i].Reason < weak[j].Reason })
	sort.Slice(ret, func(i, j int) bool { return ret[i].Reason < ret[j].Reason })
	sort.Slice(guars, func(i, j int) bool {
		if guars[i].KeyID != guars[j].KeyID {
			return guars[i].KeyID < guars[j].KeyID
		}
		return guars[i].ObjectID < guars[j].ObjectID
	})
	sort.Slice(stales, func(i, j int) bool {
		if stales[i].Subject != stales[j].Subject {
			return stales[i].Subject < stales[j].Subject
		}
		return stales[i].Kind < stales[j].Kind
	})
	sort.Slice(forges, func(i, j int) bool { return forges[i].Signer < forges[j].Signer })
	sort.Slice(corrs, func(i, j int) bool { return corrs[i].ShardID < corrs[j].ShardID })
	sort.Slice(resils, func(i, j int) bool { return resils[i].TestID < resils[j].TestID })
	sort.Slice(findings, func(i, j int) bool {
		if findings[i].Kind != findings[j].Kind {
			return findings[i].Kind < findings[j].Kind
		}
		if findings[i].Subject != findings[j].Subject {
			return findings[i].Subject < findings[j].Subject
		}
		return findings[i].Detail < findings[j].Detail
	})
	sort.Slice(evidence, func(i, j int) bool {
		if evidence[i].Kind != evidence[j].Kind {
			return evidence[i].Kind < evidence[j].Kind
		}
		return evidence[i].Ref < evidence[j].Ref
	})

	score := 0
	for _, f := range findings {
		score += weight(f.Kind, p)
	}
	if score > p.Scoring.Cap {
		score = p.Scoring.Cap
	}
	tw := p.Scoring.Cap - score

	return schema.ArchiveResult{
		ArchiveID:              a.ArchiveID,
		TrustTier:             tierFor(score, p),
		RiskScore:              score,
		Trustworthiness:        tw,
		Findings:               emptyFindings(findings),
		CoverageGaps:           emptyGaps(gaps),
		UnauthorizedMutations:  emptyMuts(muts),
		EscrowBreaks:           emptyEscrows(escrows),
		RecoveryWeaknesses:     emptyWeak(weak),
		RetentionTampers:       emptyRet(ret),
		RecoveryGuaranteeFails: emptyGuars(guars),
		StaleDependencies:      emptyStales(stales),
		RestoreForgeries:       emptyForges(forges),
		SilentCorruptions:      emptyCorrs(corrs),
		ResilienceFails:        emptyResils(resils),
		Evidence:               emptyEvidence(evidence),
	}
}

func weight(kind string, p schema.Policy) int {
	switch kind {
	case "coverage_gap":
		return p.Scoring.CoverageGap
	case "unauthorized_mutation":
		return p.Scoring.UnauthorizedMutation
	case "escrow_break":
		return p.Scoring.EscrowBreak
	case "recovery_weakness":
		return p.Scoring.RecoveryWeakness
	case "retention_tamper":
		return p.Scoring.RetentionTamper
	case "recovery_guarantee_fail":
		return p.Scoring.RecoveryGuaranteeFail
	case "stale_dependency":
		return p.Scoring.StaleDependency
	case "restore_forgery":
		return p.Scoring.RestoreForgery
	case "silent_corruption":
		return p.Scoring.SilentCorruption
	case "resilience_fail":
		return p.Scoring.ResilienceFail
	default:
		return 0
	}
}

func tierFor(score int, p schema.Policy) string {
	order := []string{"low", "medium", "high", "critical"}
	for _, name := range order {
		t, ok := p.Tiers[name]
		if !ok {
			continue
		}
		if score >= t.Min && score <= t.Max {
			return name
		}
	}
	return "critical"
}

func setOf(items []string) map[string]bool {
	m := map[string]bool{}
	for _, i := range items {
		m[i] = true
	}
	return m
}

func emptyFindings(v []schema.Finding) []schema.Finding {
	if v == nil {
		return []schema.Finding{}
	}
	return v
}
func emptyGaps(v []schema.CoverageGap) []schema.CoverageGap {
	if v == nil {
		return []schema.CoverageGap{}
	}
	return v
}
func emptyMuts(v []schema.UnauthorizedMutation) []schema.UnauthorizedMutation {
	if v == nil {
		return []schema.UnauthorizedMutation{}
	}
	return v
}
func emptyEscrows(v []schema.EscrowBreak) []schema.EscrowBreak {
	if v == nil {
		return []schema.EscrowBreak{}
	}
	return v
}
func emptyWeak(v []schema.RecoveryWeakness) []schema.RecoveryWeakness {
	if v == nil {
		return []schema.RecoveryWeakness{}
	}
	return v
}
func emptyRet(v []schema.RetentionTamper) []schema.RetentionTamper {
	if v == nil {
		return []schema.RetentionTamper{}
	}
	return v
}
func emptyGuars(v []schema.RecoveryGuaranteeFail) []schema.RecoveryGuaranteeFail {
	if v == nil {
		return []schema.RecoveryGuaranteeFail{}
	}
	return v
}
func emptyStales(v []schema.StaleDependency) []schema.StaleDependency {
	if v == nil {
		return []schema.StaleDependency{}
	}
	return v
}
func emptyForges(v []schema.RestoreForgery) []schema.RestoreForgery {
	if v == nil {
		return []schema.RestoreForgery{}
	}
	return v
}
func emptyCorrs(v []schema.SilentCorruption) []schema.SilentCorruption {
	if v == nil {
		return []schema.SilentCorruption{}
	}
	return v
}
func emptyResils(v []schema.ResilienceFail) []schema.ResilienceFail {
	if v == nil {
		return []schema.ResilienceFail{}
	}
	return v
}
func emptyEvidence(v []schema.Evidence) []schema.Evidence {
	if v == nil {
		return []schema.Evidence{}
	}
	return v
}
