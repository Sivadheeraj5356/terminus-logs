package main

import (
	"encoding/json"
	"fmt"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
)

type frameRow struct {
	ID                  string   `json:"id"`
	PriorWeight         string   `json:"prior_weight"`
	DetectorBias        []string `json:"detector_bias"`
	ForbiddenMechanisms []string `json:"forbidden_mechanisms"`
	ForbiddenBursts     []string `json:"forbidden_bursts"`
}

type familyRow struct {
	ID              string `json:"id"`
	OccurrenceLimit int    `json:"occurrence_limit"`
	WindowRounds    int    `json:"window_rounds"`
	WindowLimit     int    `json:"window_limit"`
}

type mechanismRow struct {
	ID               string              `json:"id"`
	FamilyID         string              `json:"family_id"`
	Cycle            int                 `json:"cycle"`
	CouplerID        string              `json:"coupler_id"`
	NegLogWeight     string              `json:"neg_log_weight"`
	DetectionEvents  []string            `json:"detection_events"`
	LogicalOperators []string            `json:"logical_operators"`
	DelayedEvents    map[string][]string `json:"delayed_detection_events"`
	RecoveryRounds   int                 `json:"recovery_rounds"`
}

type burstRow struct {
	ID                       string              `json:"id"`
	FamilyID                 string              `json:"family_id"`
	PriorWeight              string              `json:"prior_weight"`
	ExclusiveGroup           *string             `json:"exclusive_group"`
	StartRound               int                 `json:"start_round"`
	DurationRounds           int                 `json:"duration_rounds"`
	Intensity                int                 `json:"intensity"`
	BlockedCouplerIDs        []string            `json:"blocked_coupler_ids"`
	DetectionEventsByOffset  map[string][]string `json:"detection_events_by_offset"`
	LogicalOperatorsByOffset map[string][]string `json:"logical_operators_by_offset"`
}

type shotRow struct {
	ID                  string         `json:"id"`
	Round               int            `json:"round"`
	MeasuredEvents      []string       `json:"measured_events"`
	CandidateMechanisms []string       `json:"candidate_mechanisms"`
	CycleCaps           map[string]int `json:"cycle_caps"`
	BurstCap            int            `json:"burst_cap"`
}

type experimentInput struct {
	Schema             string         `json:"schema"`
	Stabilizers        []string       `json:"stabilizers"`
	LogicalObservables []string       `json:"logical_observables"`
	Frames             []frameRow     `json:"readout_frames"`
	Families           []familyRow    `json:"noise_families"`
	Mechanisms         []mechanismRow `json:"pauli_mechanisms"`
	BurstExposureLimit int            `json:"burst_exposure_limit"`
	Bursts             []burstRow     `json:"burst_sources"`
	Shots              []shotRow      `json:"shots"`
}

type localOption struct {
	MechanismIDs      []string
	Weight            *big.Rat
	LogicalIDs        []string
	LogicalBits       string
	FamilyOccurrences []int
	ByCycle           map[int][]string
	LocalEvents       []string
}

type objective struct {
	TotalWeight    *big.Rat
	BurstExposure  int
	PeakShotWeight *big.Rat
	BurstCount     int
	MechanismCount int
}

type representativeChoice struct {
	FrameIndex      int
	Bursts          []burstRow
	BurstEvents     [][]string
	BurstLogical    [][]string
	BurstLoads      []int
	BurstFamilyUses []int
	Options         []*localOption
	Inherited       [][]string
	Key             string
}

type readoutFrameSpectrum struct {
	ID           string   `json:"id"`
	PriorWeight  string   `json:"prior_weight"`
	DetectorBias []string `json:"detector_bias"`
}

type cycleSpectrum struct {
	Cycle        int      `json:"cycle"`
	MechanismIDs []string `json:"mechanism_ids"`
}

type shotSpectrum struct {
	ID                string          `json:"id"`
	Round             int             `json:"round"`
	MeasuredEvents    []string        `json:"measured_events"`
	BurstEvents       []string        `json:"burst_events"`
	InheritedEvents   []string        `json:"inherited_events"`
	ActiveMechanisms  []string        `json:"active_mechanisms"`
	ReproducedEvents  []string        `json:"reproduced_events"`
	BurstLogicalCoset []string        `json:"burst_logical_coset"`
	LogicalCoset      []string        `json:"logical_coset"`
	BurstLoad         int             `json:"burst_load"`
	NegLogWeight      string          `json:"neg_log_weight"`
	MechanismsByCycle []cycleSpectrum `json:"mechanisms_by_cycle"`
}

type selectedBurstSpectrum struct {
	ID                string   `json:"id"`
	FamilyID          string   `json:"family_id"`
	PriorWeight       string   `json:"prior_weight"`
	ExclusiveGroup    *string  `json:"exclusive_group"`
	StartRound        int      `json:"start_round"`
	EndRound          int      `json:"end_round"`
	Intensity         int      `json:"intensity"`
	Exposure          int      `json:"exposure"`
	BlockedCouplerIDs []string `json:"blocked_coupler_ids"`
}

type familyOccupancySpectrum struct {
	FamilyID             string `json:"family_id"`
	PauliOccurrences     int    `json:"pauli_occurrences"`
	BurstOccurrences     int    `json:"burst_occurrences"`
	ActiveOccurrences    int    `json:"active_occurrences"`
	OccurrenceLimit      int    `json:"occurrence_limit"`
	RemainingOccurrences int    `json:"remaining_occurrences"`
}

type frameSupportSpectrum struct {
	FrameID string `json:"frame_id"`
	Count   int64  `json:"count"`
}

type logicalSupportSpectrum struct {
	ClassKey string `json:"class_key"`
	Count    int64  `json:"count"`
}

type burstSupportSpectrum struct {
	BurstID string `json:"burst_id"`
	Count   int64  `json:"count"`
}

type likelihoodManifoldSpectrum struct {
	TotalNegLogWeight   string                   `json:"total_neg_log_weight"`
	BurstExposure       int                      `json:"burst_exposure"`
	PeakShotWeight      string                   `json:"peak_shot_weight"`
	BurstCount          int                      `json:"burst_count"`
	MechanismCount      int                      `json:"mechanism_count"`
	Multiplicity        int64                    `json:"multiplicity"`
	FrameSupport        []frameSupportSpectrum   `json:"frame_support"`
	BurstSupport        []burstSupportSpectrum   `json:"burst_support"`
	JointLogicalSupport []logicalSupportSpectrum `json:"joint_logical_support"`
}

type successSpectrum struct {
	Status             string                     `json:"status"`
	ReadoutFrame       readoutFrameSpectrum       `json:"readout_frame"`
	SelectedBursts     []selectedBurstSpectrum    `json:"selected_bursts"`
	Shots              []shotSpectrum             `json:"shots"`
	FamilyOccupancy    []familyOccupancySpectrum  `json:"family_occupancy"`
	LikelihoodManifold likelihoodManifoldSpectrum `json:"likelihood_manifold"`
	RepresentativeKey  string                     `json:"representative_key"`
}

type emptySpectrum struct {
	Status         string `json:"status"`
	FramesExamined int    `json:"frames_examined"`
	ShotsExamined  int    `json:"shots_examined"`
}

func parseRat(text string) *big.Rat {
	value, ok := new(big.Rat).SetString(text)
	if !ok {
		panic("invalid compatible rational")
	}
	return value
}

func copyRat(value *big.Rat) *big.Rat {
	return new(big.Rat).Set(value)
}

func ratText(value *big.Rat) string {
	if value.Denom().Cmp(big.NewInt(1)) == 0 {
		return value.Num().String()
	}
	return value.RatString()
}

func sortedCopy(values []string) []string {
	result := make([]string, len(values))
	copy(result, values)
	sort.Strings(result)
	return result
}

func sliceCopy(values []string) []string {
	result := make([]string, len(values))
	copy(result, values)
	return result
}

func matrixCopy(values [][]string) [][]string {
	result := make([][]string, len(values))
	for index, row := range values {
		result[index] = sliceCopy(row)
	}
	return result
}

func toggle(set map[string]bool, values []string) {
	for _, value := range values {
		set[value] = !set[value]
	}
}

func setMatches(left map[string]bool, right []string) bool {
	expected := make(map[string]bool, len(right))
	for _, value := range right {
		expected[value] = true
	}
	for key, present := range left {
		if present != expected[key] {
			return false
		}
		delete(expected, key)
	}
	return len(expected) == 0
}

func presentValues(values map[string]bool) []string {
	result := make([]string, 0)
	for value, present := range values {
		if present {
			result = append(result, value)
		}
	}
	sort.Strings(result)
	return result
}

func localOptions(
	shot shotRow,
	frame frameRow,
	mechanisms map[string]mechanismRow,
	familyIndex map[string]int,
	logicalOrder []string,
	blockedCouplers map[string]bool,
) []*localOption {
	forbidden := make(map[string]bool)
	for _, id := range frame.ForbiddenMechanisms {
		forbidden[id] = true
	}
	candidate := make([]mechanismRow, 0, len(shot.CandidateMechanisms))
	for _, id := range shot.CandidateMechanisms {
		if !forbidden[id] && !blockedCouplers[mechanisms[id].CouplerID] {
			candidate = append(candidate, mechanisms[id])
		}
	}
	sort.Slice(candidate, func(i, j int) bool { return candidate[i].ID < candidate[j].ID })
	options := make([]*localOption, 0)
	limit := 1 << len(candidate)
	for mask := 0; mask < limit; mask++ {
		detectorParity := make(map[string]bool)
		toggle(detectorParity, frame.DetectorBias)
		logicalParity := make(map[string]bool)
		couplers := make(map[string]bool)
		cycleCounts := make(map[int]int)
		byCycle := make(map[int][]string)
		familyUses := make([]int, len(familyIndex))
		active := make([]string, 0)
		weight := new(big.Rat)
		valid := true
		for bit, mechanism := range candidate {
			if mask&(1<<bit) == 0 {
				continue
			}
			couplerKey := strconv.Itoa(mechanism.Cycle) + "|" + mechanism.CouplerID
			if couplers[couplerKey] {
				valid = false
				break
			}
			couplers[couplerKey] = true
			cycleCounts[mechanism.Cycle]++
			if cycleCounts[mechanism.Cycle] > shot.CycleCaps[strconv.Itoa(mechanism.Cycle)] {
				valid = false
				break
			}
			active = append(active, mechanism.ID)
			byCycle[mechanism.Cycle] = append(byCycle[mechanism.Cycle], mechanism.ID)
			familyUses[familyIndex[mechanism.FamilyID]]++
			weight.Add(weight, parseRat(mechanism.NegLogWeight))
			toggle(detectorParity, mechanism.DetectionEvents)
			toggle(logicalParity, mechanism.LogicalOperators)
		}
		if !valid {
			continue
		}
		logicalIDs := make([]string, 0)
		var bits strings.Builder
		for _, id := range logicalOrder {
			if logicalParity[id] {
				bits.WriteByte('1')
				logicalIDs = append(logicalIDs, id)
			} else {
				bits.WriteByte('0')
			}
		}
		options = append(options, &localOption{
			MechanismIDs:      active,
			Weight:            weight,
			LogicalIDs:        logicalIDs,
			LogicalBits:       bits.String(),
			FamilyOccurrences: familyUses,
			ByCycle:           byCycle,
			LocalEvents:       presentValues(detectorParity),
		})
	}
	return options
}

func compareObjective(left objective, right objective) int {
	if comparison := left.TotalWeight.Cmp(right.TotalWeight); comparison != 0 {
		return comparison
	}
	if left.BurstExposure < right.BurstExposure {
		return -1
	}
	if left.BurstExposure > right.BurstExposure {
		return 1
	}
	if comparison := left.PeakShotWeight.Cmp(right.PeakShotWeight); comparison != 0 {
		return comparison
	}
	if left.BurstCount < right.BurstCount {
		return -1
	}
	if left.BurstCount > right.BurstCount {
		return 1
	}
	if left.MechanismCount < right.MechanismCount {
		return -1
	}
	if left.MechanismCount > right.MechanismCount {
		return 1
	}
	return 0
}

func representativeKey(frameID string, bursts []burstRow, shots []shotRow, options []*localOption) string {
	burstIDs := make([]string, len(bursts))
	for index, burst := range bursts {
		burstIDs[index] = burst.ID
	}
	parts := []string{frameID, "bursts=" + strings.Join(burstIDs, ",")}
	for index, shot := range shots {
		parts = append(parts, shot.ID+"="+strings.Join(options[index].MechanismIDs, ","))
	}
	return strings.Join(parts, "|")
}

func logicalClassKey(shots []shotRow, options []*localOption, burstLogical [][]string, logicalOrder []string) string {
	parts := make([]string, len(shots))
	for index, shot := range shots {
		parity := make(map[string]bool)
		toggle(parity, options[index].LogicalIDs)
		toggle(parity, burstLogical[index])
		var bits strings.Builder
		for _, logicalID := range logicalOrder {
			if parity[logicalID] {
				bits.WriteByte('1')
			} else {
				bits.WriteByte('0')
			}
		}
		parts[index] = shot.ID + ":" + bits.String()
	}
	return strings.Join(parts, "/")
}

func solve(experiment experimentInput) any {
	mechanisms := make(map[string]mechanismRow, len(experiment.Mechanisms))
	for _, mechanism := range experiment.Mechanisms {
		mechanisms[mechanism.ID] = mechanism
	}
	families := append([]familyRow(nil), experiment.Families...)
	sort.Slice(families, func(i, j int) bool { return families[i].ID < families[j].ID })
	familyIndex := make(map[string]int, len(families))
	for index, family := range families {
		familyIndex[family.ID] = index
	}
	shots := append([]shotRow(nil), experiment.Shots...)
	sort.Slice(shots, func(i, j int) bool {
		if shots[i].Round != shots[j].Round {
			return shots[i].Round < shots[j].Round
		}
		return shots[i].ID < shots[j].ID
	})

	var best *objective
	var representative *representativeChoice
	var multiplicity int64
	frameSupport := make(map[string]int64)
	burstSupport := make(map[string]int64)
	logicalSupport := make(map[string]int64)
	bursts := append([]burstRow(nil), experiment.Bursts...)
	sort.Slice(bursts, func(i, j int) bool { return bursts[i].ID < bursts[j].ID })

	for frameIndex, frame := range experiment.Frames {
		forbiddenBursts := make(map[string]bool)
		for _, burstID := range frame.ForbiddenBursts {
			forbiddenBursts[burstID] = true
		}
		availableBursts := make([]burstRow, 0, len(bursts))
		for _, burst := range bursts {
			if !forbiddenBursts[burst.ID] {
				availableBursts = append(availableBursts, burst)
			}
		}
		burstLimit := 1 << len(availableBursts)
		for burstMask := 0; burstMask < burstLimit; burstMask++ {
			selectedBursts := make([]burstRow, 0)
			burstGroups := make(map[string]bool)
			burstExposure := 0
			burstWeight := new(big.Rat)
			burstFamilyUses := make([]int, len(families))
			burstValid := true
			for bit, burst := range availableBursts {
				if burstMask&(1<<bit) == 0 {
					continue
				}
				if burst.ExclusiveGroup != nil {
					group := *burst.ExclusiveGroup
					if burstGroups[group] {
						burstValid = false
						break
					}
					burstGroups[group] = true
				}
				selectedBursts = append(selectedBursts, burst)
				burstExposure += burst.Intensity * burst.DurationRounds
				burstWeight.Add(burstWeight, parseRat(burst.PriorWeight))
				burstFamilyUses[familyIndex[burst.FamilyID]]++
			}
			if !burstValid || burstExposure > experiment.BurstExposureLimit {
				continue
			}
			for family, count := range burstFamilyUses {
				if count > families[family].OccurrenceLimit {
					burstValid = false
					break
				}
			}
			if !burstValid {
				continue
			}

			burstEvents := make([][]string, len(shots))
			burstLogical := make([][]string, len(shots))
			burstLoads := make([]int, len(shots))
			blockedCouplers := make([]map[string]bool, len(shots))
			allOptions := make([][]*localOption, len(shots))
			for index, shot := range shots {
				eventParity := make(map[string]bool)
				logicalParity := make(map[string]bool)
				blockedCouplers[index] = make(map[string]bool)
				for _, burst := range selectedBursts {
					offset := shot.Round - burst.StartRound
					if offset < 0 || offset >= burst.DurationRounds {
						continue
					}
					burstLoads[index] += burst.Intensity
					for _, couplerID := range burst.BlockedCouplerIDs {
						blockedCouplers[index][couplerID] = true
					}
					toggle(eventParity, burst.DetectionEventsByOffset[strconv.Itoa(offset)])
					toggle(logicalParity, burst.LogicalOperatorsByOffset[strconv.Itoa(offset)])
				}
				if burstLoads[index] > shot.BurstCap {
					burstValid = false
					break
				}
				burstEvents[index] = presentValues(eventParity)
				burstLogical[index] = presentValues(logicalParity)
				allOptions[index] = localOptions(
					shot, frame, mechanisms, familyIndex, experiment.LogicalObservables, blockedCouplers[index],
				)
			}
			if !burstValid {
				continue
			}

			chosen := make([]*localOption, len(shots))
			chosenInherited := make([][]string, len(shots))
			uses := append([]int(nil), burstFamilyUses...)
			var visit func(int, *big.Rat, *big.Rat, int)
			visit = func(index int, mechanismTotal *big.Rat, worst *big.Rat, mechanismCount int) {
				if index == len(shots) {
					total := new(big.Rat).Add(parseRat(frame.PriorWeight), burstWeight)
					total.Add(total, mechanismTotal)
					candidateObjective := objective{
						TotalWeight: total, BurstExposure: burstExposure, PeakShotWeight: copyRat(worst),
						BurstCount: len(selectedBursts), MechanismCount: mechanismCount,
					}
					key := representativeKey(frame.ID, selectedBursts, shots, chosen)
					classKey := logicalClassKey(shots, chosen, burstLogical, experiment.LogicalObservables)
					comparison := -1
					if best != nil {
						comparison = compareObjective(candidateObjective, *best)
					}
					choice := func() *representativeChoice {
						return &representativeChoice{
							FrameIndex: frameIndex, Bursts: append([]burstRow(nil), selectedBursts...),
							BurstEvents: matrixCopy(burstEvents), BurstLogical: matrixCopy(burstLogical),
							BurstLoads: append([]int(nil), burstLoads...), BurstFamilyUses: append([]int(nil), burstFamilyUses...),
							Options: append([]*localOption(nil), chosen...), Inherited: matrixCopy(chosenInherited), Key: key,
						}
					}
					if best == nil || comparison < 0 {
						bestCopy := objective{
							TotalWeight: copyRat(candidateObjective.TotalWeight), BurstExposure: candidateObjective.BurstExposure,
							PeakShotWeight: copyRat(candidateObjective.PeakShotWeight), BurstCount: candidateObjective.BurstCount,
							MechanismCount: candidateObjective.MechanismCount,
						}
						best = &bestCopy
						multiplicity = 1
						frameSupport = map[string]int64{frame.ID: 1}
						burstSupport = make(map[string]int64)
						for _, burst := range selectedBursts {
							burstSupport[burst.ID] = 1
						}
						logicalSupport = map[string]int64{classKey: 1}
						representative = choice()
					} else if comparison == 0 {
						multiplicity++
						frameSupport[frame.ID]++
						for _, burst := range selectedBursts {
							burstSupport[burst.ID]++
						}
						logicalSupport[classKey]++
						if key < representative.Key {
							representative = choice()
						}
					}
					return
				}
				for _, option := range allOptions[index] {
					valid := true
					for family, count := range option.FamilyOccurrences {
						if uses[family]+count > families[family].OccurrenceLimit {
							valid = false
							break
						}
					}
					if !valid {
						continue
					}
					inheritedParity := make(map[string]bool)
					for earlierIndex := 0; earlierIndex < index; earlierIndex++ {
						delta := shots[index].Round - shots[earlierIndex].Round
						for _, earlierID := range chosen[earlierIndex].MechanismIDs {
							earlier := mechanisms[earlierID]
							toggle(inheritedParity, earlier.DelayedEvents[strconv.Itoa(delta)])
						}
					}
					reproduced := make(map[string]bool)
					toggle(reproduced, option.LocalEvents)
					toggle(reproduced, presentValues(inheritedParity))
					toggle(reproduced, burstEvents[index])
					if !setMatches(reproduced, shots[index].MeasuredEvents) {
						continue
					}
					for _, mechanismID := range option.MechanismIDs {
						current := mechanisms[mechanismID]
						for earlierIndex := 0; earlierIndex < index && valid; earlierIndex++ {
							delta := shots[index].Round - shots[earlierIndex].Round
							for _, earlierID := range chosen[earlierIndex].MechanismIDs {
								earlier := mechanisms[earlierID]
								if earlier.Cycle == current.Cycle && earlier.CouplerID == current.CouplerID && delta <= earlier.RecoveryRounds {
									valid = false
									break
								}
							}
						}
					}
					if !valid {
						continue
					}
					for familyNumber, family := range families {
						windowUses := option.FamilyOccurrences[familyNumber]
						for earlierIndex := 0; earlierIndex < index; earlierIndex++ {
							if shots[index].Round-shots[earlierIndex].Round < family.WindowRounds {
								windowUses += chosen[earlierIndex].FamilyOccurrences[familyNumber]
							}
						}
						for _, burst := range selectedBursts {
							delta := shots[index].Round - burst.StartRound
							if burst.FamilyID == family.ID && delta >= 0 && delta < family.WindowRounds {
								windowUses++
							}
						}
						if windowUses > family.WindowLimit {
							valid = false
							break
						}
					}
					if !valid {
						continue
					}
					for family, count := range option.FamilyOccurrences {
						uses[family] += count
					}
					chosen[index] = option
					chosenInherited[index] = presentValues(inheritedParity)
					nextTotal := new(big.Rat).Add(mechanismTotal, option.Weight)
					nextWorst := copyRat(worst)
					if option.Weight.Cmp(nextWorst) > 0 {
						nextWorst.Set(option.Weight)
					}
					visit(index+1, nextTotal, nextWorst, mechanismCount+len(option.MechanismIDs))
					for family, count := range option.FamilyOccurrences {
						uses[family] -= count
					}
				}
			}
			visit(0, new(big.Rat), new(big.Rat), 0)
		}
	}

	if best == nil {
		return emptySpectrum{Status: "no_physical_coset", FramesExamined: len(experiment.Frames), ShotsExamined: len(experiment.Shots)}
	}

	frame := experiment.Frames[representative.FrameIndex]
	shotSpectrums := make([]shotSpectrum, len(shots))
	representativePauliUses := make([]int, len(families))
	for index, shot := range shots {
		option := representative.Options[index]
		cycles := make([]int, 0, len(option.ByCycle))
		for cycle := range option.ByCycle {
			cycles = append(cycles, cycle)
		}
		sort.Ints(cycles)
		byCycle := make([]cycleSpectrum, 0, len(cycles))
		for _, cycle := range cycles {
			byCycle = append(byCycle, cycleSpectrum{Cycle: cycle, MechanismIDs: sortedCopy(option.ByCycle[cycle])})
		}
		for family, count := range option.FamilyOccurrences {
			representativePauliUses[family] += count
		}
		logicalParity := make(map[string]bool)
		toggle(logicalParity, option.LogicalIDs)
		toggle(logicalParity, representative.BurstLogical[index])
		totalLogical := make([]string, 0)
		for _, logicalID := range experiment.LogicalObservables {
			if logicalParity[logicalID] {
				totalLogical = append(totalLogical, logicalID)
			}
		}
		measured := sortedCopy(shot.MeasuredEvents)
		shotSpectrums[index] = shotSpectrum{
			ID:                shot.ID,
			Round:             shot.Round,
			MeasuredEvents:    measured,
			BurstEvents:       sliceCopy(representative.BurstEvents[index]),
			InheritedEvents:   sliceCopy(representative.Inherited[index]),
			ActiveMechanisms:  sliceCopy(option.MechanismIDs),
			ReproducedEvents:  sliceCopy(measured),
			BurstLogicalCoset: sliceCopy(representative.BurstLogical[index]),
			LogicalCoset:      totalLogical,
			BurstLoad:         representative.BurstLoads[index],
			NegLogWeight:      ratText(option.Weight),
			MechanismsByCycle: byCycle,
		}
	}

	selectedBurstSpectrums := make([]selectedBurstSpectrum, len(representative.Bursts))
	for index, burst := range representative.Bursts {
		selectedBurstSpectrums[index] = selectedBurstSpectrum{
			ID: burst.ID, FamilyID: burst.FamilyID, PriorWeight: ratText(parseRat(burst.PriorWeight)),
			ExclusiveGroup: burst.ExclusiveGroup, StartRound: burst.StartRound,
			EndRound: burst.StartRound + burst.DurationRounds - 1, Intensity: burst.Intensity,
			Exposure: burst.Intensity * burst.DurationRounds, BlockedCouplerIDs: sortedCopy(burst.BlockedCouplerIDs),
		}
	}

	familySpectrums := make([]familyOccupancySpectrum, len(families))
	for index, family := range families {
		active := representativePauliUses[index] + representative.BurstFamilyUses[index]
		familySpectrums[index] = familyOccupancySpectrum{
			FamilyID: family.ID, PauliOccurrences: representativePauliUses[index],
			BurstOccurrences: representative.BurstFamilyUses[index], ActiveOccurrences: active,
			OccurrenceLimit: family.OccurrenceLimit, RemainingOccurrences: family.OccurrenceLimit - active,
		}
	}

	frames := append([]frameRow(nil), experiment.Frames...)
	sort.Slice(frames, func(i, j int) bool { return frames[i].ID < frames[j].ID })
	frameSpectrums := make([]frameSupportSpectrum, len(frames))
	for index, candidate := range frames {
		frameSpectrums[index] = frameSupportSpectrum{FrameID: candidate.ID, Count: frameSupport[candidate.ID]}
	}
	burstSpectrums := make([]burstSupportSpectrum, len(bursts))
	for index, burst := range bursts {
		burstSpectrums[index] = burstSupportSpectrum{BurstID: burst.ID, Count: burstSupport[burst.ID]}
	}
	classKeys := make([]string, 0, len(logicalSupport))
	for key := range logicalSupport {
		classKeys = append(classKeys, key)
	}
	sort.Strings(classKeys)
	logicalSpectrums := make([]logicalSupportSpectrum, len(classKeys))
	for index, key := range classKeys {
		logicalSpectrums[index] = logicalSupportSpectrum{ClassKey: key, Count: logicalSupport[key]}
	}

	return successSpectrum{
		Status:          "resolved",
		ReadoutFrame:    readoutFrameSpectrum{ID: frame.ID, PriorWeight: ratText(parseRat(frame.PriorWeight)), DetectorBias: sortedCopy(frame.DetectorBias)},
		SelectedBursts:  selectedBurstSpectrums,
		Shots:           shotSpectrums,
		FamilyOccupancy: familySpectrums,
		LikelihoodManifold: likelihoodManifoldSpectrum{
			TotalNegLogWeight: ratText(best.TotalWeight), BurstExposure: best.BurstExposure,
			PeakShotWeight: ratText(best.PeakShotWeight), BurstCount: best.BurstCount, MechanismCount: best.MechanismCount,
			Multiplicity: multiplicity, FrameSupport: frameSpectrums, BurstSupport: burstSpectrums,
			JointLogicalSupport: logicalSpectrums,
		},
		RepresentativeKey: representative.Key,
	}
}

func main() {
	if len(os.Args) != 3 {
		fmt.Fprintln(os.Stderr, "usage: infer_stabilizer_burst_cosets OBSERVATIONS COSET_SPECTRUM")
		os.Exit(2)
	}
	inputBytes, err := os.ReadFile(os.Args[1])
	if err != nil {
		panic(err)
	}
	var experiment experimentInput
	if err := json.Unmarshal(inputBytes, &experiment); err != nil {
		panic(err)
	}
	spectrum := solve(experiment)
	outputBytes, err := json.MarshalIndent(spectrum, "", "  ")
	if err != nil {
		panic(err)
	}
	if err := os.MkdirAll(filepath.Dir(os.Args[2]), 0o755); err != nil {
		panic(err)
	}
	outputBytes = append(outputBytes, '\n')
	if err := os.WriteFile(os.Args[2], outputBytes, 0o644); err != nil {
		panic(err)
	}
}
