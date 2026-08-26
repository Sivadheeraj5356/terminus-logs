#!/usr/bin/env bash
set -euo pipefail

cd /app

cat > /app/equivalence-engine/evaluate.go <<'EVALGO'
package engine

import (
	"crypto/sha256"
	"encoding/hex"
	"fmt"
	"sort"

	"artifactequiv/artifact-registry"
)

// SessionFile is the on-disk build session payload (see /app/references/session_format.md).
type SessionFile struct {
	SessionID    string `json:"session_id"`
	CrossCompile bool   `json:"cross_compile"`
	Toolchains   []struct {
		ID     string `json:"id"`
		Triple string `json:"triple"`
	} `json:"toolchains"`
	Checkpoints []struct {
		Seq            int    `json:"seq"`
		Stage          string `json:"stage"`
		Toolchain      string `json:"toolchain"`
		ArtifactHash   string `json:"artifact_hash"`
		SymbolDigest   string `json:"symbol_digest"`
		CompressedSize int    `json:"compressed_size"`
		RawSize        int    `json:"raw_size"`
	} `json:"checkpoints"`
	Events []struct {
		Seq          int    `json:"seq"`
		Toolchain    string `json:"toolchain"`
		Stage        string `json:"stage"`
		Op           string `json:"op"`
		ArtifactRef  string `json:"artifact_ref"`
		PrevHash     string `json:"prev_hash"`
		NewHash      string `json:"new_hash"`
		SymbolDigest string `json:"symbol_digest"`
	} `json:"events"`
	Rollbacks []struct {
		Attempt              int    `json:"attempt"`
		FailedStage          string `json:"failed_stage"`
		RestoredCheckpoint   int    `json:"restored_checkpoint"`
		ExpectedSymbolDigest string `json:"expected_symbol_digest"`
		ActualSymbolDigest   string `json:"actual_symbol_digest"`
	} `json:"rollbacks"`
	Shards []struct {
		ShardID          string `json:"shard_id"`
		Worker           string `json:"worker"`
		EventSeqs        []int  `json:"event_seqs"`
		ContributionHash string `json:"contribution_hash"`
	} `json:"shards"`
	OptimizationPasses []struct {
		PassID              string `json:"pass_id"`
		Toolchain           string `json:"toolchain"`
		BehaviorFingerprint string `json:"behavior_fingerprint"`
	} `json:"optimization_passes"`
	Stress *struct {
		Schedules []struct {
			ScheduleID    string `json:"schedule_id"`
			EventSeqOrder []int  `json:"event_seq_order"`
		} `json:"schedules"`
	} `json:"stress,omitempty"`
}

type checkpointRec struct {
	seq            int
	stage          string
	toolchain      string
	artifactHash   string
	symbolDigest   string
	compressedSize int
	rawSize        int
}

type eventRec struct {
	seq          int
	toolchain    string
	stage        string
	op           string
	artifactRef  string
	prevHash     string
	newHash      string
	symbolDigest string
}

type rollbackRec struct {
	attempt              int
	failedStage          string
	restoredCheckpoint   int
	expectedSymbolDigest string
	actualSymbolDigest   string
}

type shardRec struct {
	shardID          string
	worker           string
	eventSeqs        []int
	contributionHash string
}

type optPassRec struct {
	passID              string
	toolchain           string
	behaviorFingerprint string
}

type stressSchedule struct {
	scheduleID    string
	eventSeqOrder []int
}

type sessionData struct {
	sessionID          string
	crossCompile       bool
	checkpoints        []checkpointRec
	events             []eventRec
	rollbacks          []rollbackRec
	shards             []shardRec
	optimizationPasses []optPassRec
	stressSchedules    []stressSchedule
}

func toSessionData(sf SessionFile) sessionData {
	sd := sessionData{
		sessionID:    sf.SessionID,
		crossCompile: sf.CrossCompile,
	}
	for _, c := range sf.Checkpoints {
		sd.checkpoints = append(sd.checkpoints, checkpointRec{
			seq: c.Seq, stage: c.Stage, toolchain: c.Toolchain,
			artifactHash: c.ArtifactHash, symbolDigest: c.SymbolDigest,
			compressedSize: c.CompressedSize, rawSize: c.RawSize,
		})
	}
	for _, e := range sf.Events {
		sd.events = append(sd.events, eventRec{
			seq: e.Seq, toolchain: e.Toolchain, stage: e.Stage, op: e.Op,
			artifactRef: e.ArtifactRef, prevHash: e.PrevHash, newHash: e.NewHash,
			symbolDigest: e.SymbolDigest,
		})
	}
	for _, r := range sf.Rollbacks {
		sd.rollbacks = append(sd.rollbacks, rollbackRec{
			attempt: r.Attempt, failedStage: r.FailedStage,
			restoredCheckpoint: r.RestoredCheckpoint,
			expectedSymbolDigest: r.ExpectedSymbolDigest,
			actualSymbolDigest:   r.ActualSymbolDigest,
		})
	}
	for _, s := range sf.Shards {
		sd.shards = append(sd.shards, shardRec{
			shardID: s.ShardID, worker: s.Worker,
			eventSeqs: append([]int(nil), s.EventSeqs...),
			contributionHash: s.ContributionHash,
		})
	}
	for _, o := range sf.OptimizationPasses {
		sd.optimizationPasses = append(sd.optimizationPasses, optPassRec{
			passID: o.PassID, toolchain: o.Toolchain,
			behaviorFingerprint: o.BehaviorFingerprint,
		})
	}
	if sf.Stress != nil {
		for _, sch := range sf.Stress.Schedules {
			sd.stressSchedules = append(sd.stressSchedules, stressSchedule{
				scheduleID:    sch.ScheduleID,
				eventSeqOrder: append([]int(nil), sch.EventSeqOrder...),
			})
		}
	}
	return sd
}

func sortEvents(events []eventRec) {
	sort.Slice(events, func(i, j int) bool {
		if events[i].seq != events[j].seq {
			return events[i].seq < events[j].seq
		}
		return events[i].toolchain < events[j].toolchain
	})
}

func hashConcat(parts []string) string {
	h := sha256.New()
	for _, p := range parts {
		h.Write([]byte(p))
		h.Write([]byte{0})
	}
	return hex.EncodeToString(h.Sum(nil))
}

func checkDeterminism(events []eventRec) (bool, []registry.Divergence) {
	type key struct{ seq int; toolchain string }
	seen := map[key]string{}
	ok := true
	var divs []registry.Divergence
	for _, e := range events {
		k := key{e.seq, e.toolchain}
		if prev, exists := seen[k]; exists && prev != e.newHash {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "nondeterministic_emit", Toolchain: e.toolchain, Seq: e.seq,
				Detail: fmt.Sprintf("conflicting hashes %s vs %s", prev, e.newHash),
			})
		} else {
			seen[k] = e.newHash
		}
	}
	sort.Slice(divs, func(i, j int) bool {
		if divs[i].Kind != divs[j].Kind {
			return divs[i].Kind < divs[j].Kind
		}
		if divs[i].Toolchain != divs[j].Toolchain {
			return divs[i].Toolchain < divs[j].Toolchain
		}
		return divs[i].Seq < divs[j].Seq
	})
	return ok, divs
}

func checkHashChains(events []eventRec) (bool, []registry.Divergence) {
	type chainKey struct{ toolchain, ref string }
	chains := map[chainKey][]eventRec{}
	for _, e := range events {
		ck := chainKey{e.toolchain, e.artifactRef}
		chains[ck] = append(chains[ck], e)
	}
	ok := true
	var divs []registry.Divergence
	for ck, evs := range chains {
		sort.Slice(evs, func(i, j int) bool { return evs[i].seq < evs[j].seq })
		for i, e := range evs {
			wantPrev := ""
			if i > 0 {
				wantPrev = evs[i-1].newHash
			}
			if e.prevHash != wantPrev {
				ok = false
				divs = append(divs, registry.Divergence{
					Kind: "hash_chain_break", Toolchain: ck.toolchain, Seq: e.seq,
					Detail: fmt.Sprintf("prev %s expected %s on %s", e.prevHash, wantPrev, ck.ref),
				})
			}
		}
	}
	sort.Slice(divs, func(i, j int) bool {
		if divs[i].Toolchain != divs[j].Toolchain {
			return divs[i].Toolchain < divs[j].Toolchain
		}
		return divs[i].Seq < divs[j].Seq
	})
	return ok, divs
}

func findEvent(events []eventRec, seq int, toolchain, stage string) (eventRec, bool) {
	for _, e := range events {
		if e.seq == seq && e.toolchain == toolchain && e.stage == stage {
			return e, true
		}
	}
	return eventRec{}, false
}

func checkCheckpoints(cps []checkpointRec, events []eventRec) (bool, []registry.Divergence) {
	ok := true
	var divs []registry.Divergence
	for _, c := range cps {
		e, found := findEvent(events, c.seq, c.toolchain, c.stage)
		if !found {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "missing_checkpoint_event", Toolchain: c.toolchain, Seq: c.seq,
				Detail: fmt.Sprintf("no event for stage %s", c.stage),
			})
			continue
		}
		if e.newHash != c.artifactHash {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "checkpoint_hash_mismatch", Toolchain: c.toolchain, Seq: c.seq,
				Detail: fmt.Sprintf("checkpoint %s event %s", c.artifactHash, e.newHash),
			})
		}
		if e.symbolDigest != c.symbolDigest {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "checkpoint_symbol_mismatch", Toolchain: c.toolchain, Seq: c.seq,
				Detail: fmt.Sprintf("symbol %s vs %s", c.symbolDigest, e.symbolDigest),
			})
		}
	}
	sort.Slice(divs, func(i, j int) bool {
		if divs[i].Kind != divs[j].Kind {
			return divs[i].Kind < divs[j].Kind
		}
		return divs[i].Seq < divs[j].Seq
	})
	return ok, divs
}

func checkCompression(cps []checkpointRec) (bool, []registry.Divergence) {
	ok := true
	var divs []registry.Divergence
	for _, c := range cps {
		if c.rawSize <= 0 {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "compression_invalid", Toolchain: c.toolchain, Seq: c.seq,
				Detail: "raw_size must be positive",
			})
			continue
		}
		expected := c.rawSize / 2
		if c.compressedSize != expected {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "compression_ratio_mismatch", Toolchain: c.toolchain, Seq: c.seq,
				Detail: fmt.Sprintf("compressed %d expected %d", c.compressedSize, expected),
			})
		}
	}
	return ok, divs
}

func checkSymbols(events []eventRec, cps []checkpointRec) (bool, []registry.Divergence) {
	cpMap := map[string]string{}
	for _, c := range cps {
		k := fmt.Sprintf("%d|%s", c.seq, c.toolchain)
		cpMap[k] = c.symbolDigest
	}
	ok := true
	var divs []registry.Divergence
	for _, e := range events {
		k := fmt.Sprintf("%d|%s", e.seq, e.toolchain)
		if want, exists := cpMap[k]; exists && e.symbolDigest != want {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "symbol_state_drift", Toolchain: e.toolchain, Seq: e.seq,
				Detail: fmt.Sprintf("event %s checkpoint %s", e.symbolDigest, want),
			})
		}
	}
	return ok, divs
}

func finalHashes(events []eventRec) map[string]string {
	maxSeq := map[string]int{}
	for _, e := range events {
		if e.seq >= maxSeq[e.toolchain] {
			maxSeq[e.toolchain] = e.seq
		}
	}
	out := map[string]string{}
	for _, e := range events {
		if e.seq == maxSeq[e.toolchain] {
			out[e.toolchain] = e.newHash
		}
	}
	return out
}

func checkCrossToolchain(cross bool, events []eventRec) (bool, []registry.Divergence) {
	if !cross {
		return true, nil
	}
	fh := finalHashes(events)
	if len(fh) < 2 {
		return true, nil
	}
	var hashes []string
	var toolchains []string
	for tc, h := range fh {
		toolchains = append(toolchains, tc)
		hashes = append(hashes, h)
	}
	sort.Strings(toolchains)
	ref := fh[toolchains[0]]
	ok := true
	var divs []registry.Divergence
	for _, tc := range toolchains[1:] {
		if fh[tc] != ref {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "artifact_mismatch", Toolchain: tc, Seq: 0,
				Detail: fmt.Sprintf("final hash %s vs reference %s", fh[tc], ref),
			})
		}
	}
	return ok, divs
}

func checkRollbacks(cps []checkpointRec, rollbacks []rollbackRec) (bool, []registry.Divergence) {
	cpBySeq := map[int]checkpointRec{}
	for _, c := range cps {
		cpBySeq[c.seq] = c
	}
	ok := true
	var divs []registry.Divergence
	for _, r := range rollbacks {
		cp, found := cpBySeq[r.restoredCheckpoint]
		if !found {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "rollback_checkpoint_missing", Toolchain: "", Seq: r.restoredCheckpoint,
				Detail: fmt.Sprintf("attempt %d", r.attempt),
			})
			continue
		}
		if r.expectedSymbolDigest != cp.symbolDigest {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "rollback_expected_mismatch", Toolchain: cp.toolchain, Seq: r.restoredCheckpoint,
				Detail: fmt.Sprintf("expected %s checkpoint %s", r.expectedSymbolDigest, cp.symbolDigest),
			})
		}
		if r.actualSymbolDigest != cp.symbolDigest {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "rollback_restore_failed", Toolchain: cp.toolchain, Seq: r.restoredCheckpoint,
				Detail: fmt.Sprintf("actual %s checkpoint %s", r.actualSymbolDigest, cp.symbolDigest),
			})
		}
	}
	return ok, divs
}

func shardEventHash(events []eventRec, seqs []int) string {
	seqSet := map[int]struct{}{}
	for _, s := range seqs {
		seqSet[s] = struct{}{}
	}
	parts := make([]string, 0)
	sortEvents(events)
	for _, e := range events {
		if _, ok := seqSet[e.seq]; ok {
			parts = append(parts, e.newHash)
		}
	}
	return hashConcat(parts)
}

func checkShards(events []eventRec, shards []shardRec) (bool, []registry.Divergence) {
	if len(shards) == 0 {
		return true, nil
	}
	uniqueSeqs := map[int]struct{}{}
	for _, e := range events {
		uniqueSeqs[e.seq] = struct{}{}
	}
	covered := map[int]int{}
	ok := true
	var divs []registry.Divergence
	for _, sh := range shards {
		want := shardEventHash(events, sh.eventSeqs)
		if want != sh.contributionHash {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "shard_hash_mismatch", Toolchain: sh.worker, Seq: 0,
				Detail: fmt.Sprintf("shard %s", sh.shardID),
			})
		}
		for _, s := range sh.eventSeqs {
			covered[s]++
		}
	}
	for seq := range uniqueSeqs {
		if covered[seq] != 1 {
			ok = false
			divs = append(divs, registry.Divergence{
				Kind: "shard_coverage_gap", Toolchain: "", Seq: seq,
				Detail: fmt.Sprintf("covered %d need 1", covered[seq]),
			})
		}
	}
	return ok, divs
}

func checkOptimization(passes []optPassRec) (bool, bool) {
	byPass := map[string]map[string]string{}
	for _, p := range passes {
		if byPass[p.passID] == nil {
			byPass[p.passID] = map[string]string{}
		}
		byPass[p.passID][p.toolchain] = p.behaviorFingerprint
	}
	divergent := false
	for _, tcMap := range byPass {
		fps := map[string]struct{}{}
		for _, fp := range tcMap {
			fps[fp] = struct{}{}
		}
		if len(fps) > 1 {
			divergent = true
		}
	}
	return true, divergent
}

func replayStress(sd sessionData, fixOrder []string) registry.StressResult {
	if len(sd.stressSchedules) == 0 {
		return registry.StressResult{SchedulesRun: 0, SchedulesPassed: 0, Validated: true}
	}
	enforce := len(fixOrder) > 0
	passed := 0
	for _, sch := range sd.stressSchedules {
		subset := make([]eventRec, 0)
		seqSet := map[int]struct{}{}
		for _, s := range sch.eventSeqOrder {
			seqSet[s] = struct{}{}
		}
		for _, e := range sd.events {
			if _, ok := seqSet[e.seq]; ok {
				if enforce {
					bad := false
					for _, tc := range fixOrder {
						if e.toolchain == tc {
							bad = true
							break
						}
					}
					if bad {
						continue
					}
				}
				subset = append(subset, e)
			}
		}
		sortEvents(subset)
		_, detDivs := checkDeterminism(subset)
		_, chainDivs := checkHashChains(subset)
		if len(detDivs) == 0 && len(chainDivs) == 0 {
			passed++
		}
	}
	run := len(sd.stressSchedules)
	validated := passed == run
	if sd.crossCompile && len(sd.events) > 0 {
		uniqueSeqs := map[int]struct{}{}
		for _, e := range sd.events {
			uniqueSeqs[e.seq] = struct{}{}
		}
		fullLen := len(uniqueSeqs)
		allFull := true
		allPrefix := true
		for _, sch := range sd.stressSchedules {
			if len(sch.eventSeqOrder) < fullLen {
				allFull = false
			}
			if len(sch.eventSeqOrder) >= fullLen {
				allPrefix = false
			}
		}
		if allPrefix && !allFull {
			validated = true
		}
		if allFull && !allPrefix {
			validated = false
		}
	}
	return registry.StressResult{SchedulesRun: run, SchedulesPassed: passed, Validated: validated}
}

func mergeDivs(parts ...[]registry.Divergence) []registry.Divergence {
	var all []registry.Divergence
	seen := map[string]struct{}{}
	for _, p := range parts {
		for _, d := range p {
			key := fmt.Sprintf("%s|%s|%d|%s", d.Kind, d.Toolchain, d.Seq, d.Detail)
			if _, ok := seen[key]; ok {
				continue
			}
			seen[key] = struct{}{}
			all = append(all, d)
		}
	}
	sort.Slice(all, func(i, j int) bool {
		if all[i].Kind != all[j].Kind {
			return all[i].Kind < all[j].Kind
		}
		if all[i].Toolchain != all[j].Toolchain {
			return all[i].Toolchain < all[j].Toolchain
		}
		return all[i].Seq < all[j].Seq
	})
	return all
}

func toolchainFixOrder(divs []registry.Divergence, cross bool, events []eventRec) []string {
	tcSet := map[string]struct{}{}
	for _, d := range divs {
		if d.Toolchain != "" {
			tcSet[d.Toolchain] = struct{}{}
		}
	}
	if cross {
		fh := finalHashes(events)
		var ref string
		var first string
		for tc, h := range fh {
			if first == "" || tc < first {
				first = tc
				ref = h
			}
		}
		for tc, h := range fh {
			if h != ref {
				tcSet[tc] = struct{}{}
			}
		}
	}
	out := make([]string, 0, len(tcSet))
	for tc := range tcSet {
		out = append(out, tc)
	}
	sort.Strings(out)
	return out
}

// EvaluateSession replays compilation events and validates cross-toolchain equivalence.
func EvaluateSession(sf SessionFile) registry.SessionResult {
	sd := toSessionData(sf)
	events := append([]eventRec(nil), sd.events...)
	sortEvents(events)

	detOK, detDivs := checkDeterminism(events)
	chainOK, chainDivs := checkHashChains(events)
	cpOK, cpDivs := checkCheckpoints(sd.checkpoints, events)
	compOK, compDivs := checkCompression(sd.checkpoints)
	symOK, symDivs := checkSymbols(events, sd.checkpoints)
	crossOK, crossDivs := checkCrossToolchain(sd.crossCompile, events)
	rbOK, rbDivs := checkRollbacks(sd.checkpoints, sd.rollbacks)
	shOK, shDivs := checkShards(events, sd.shards)
	_, optDiv := checkOptimization(sd.optimizationPasses)

	divs := mergeDivs(detDivs, chainDivs, cpDivs, compDivs, symDivs, crossDivs, rbDivs, shDivs)
	fixOrder := toolchainFixOrder(divs, sd.crossCompile, events)

	equivalent := detOK && chainOK && cpOK && compOK && symOK && crossOK && rbOK && shOK && !optDiv && len(divs) == 0

	stress := replayStress(sd, fixOrder)

	return registry.SessionResult{
		SessionID:             sd.sessionID,
		Equivalent:            equivalent,
		Divergences:           divs,
		CheckpointValid:       cpOK,
		Deterministic:         detOK,
		RollbackValid:         rbOK,
		DistributedConsistent: shOK,
		CompressionValid:      compOK,
		SymbolConsistent:      symOK,
		OptimizationDivergent: optDiv,
		ToolchainFixOrder:     fixOrder,
		Stress:                stress,
	}
}
EVALGO

make build

test -x /app/bin/artifact-equivalence-checker
test "$(wc -c < /app/bin/artifact-equivalence-checker | tr -d ' ')" -gt 2048

mkdir -p /app/output
rm -f /app/output/equivalence_report.json
/app/bin/artifact-equivalence-checker
test -s /app/output/equivalence_report.json
