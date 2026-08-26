package main

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
)

type vSpin struct {
	ID        string `json:"id"`
	BiasMilli int64  `json:"bias_milli"`
	Initial   int    `json:"initial"`
}

type vEdge struct {
	A             string `json:"a"`
	B             string `json:"b"`
	CouplingMilli int64  `json:"coupling_milli"`
}

type vModel struct {
	Schema               string  `json:"schema"`
	InitialExternalMilli int64   `json:"initial_external_milli"`
	InitialDirection     int     `json:"initial_direction"`
	Spins                []vSpin `json:"spins"`
	Edges                []vEdge `json:"edges"`
}

type vRuntimeEdge struct {
	A, B int
	J    int64
}

type vRuntimeModel struct {
	Spins                []vSpin
	Edges                []vRuntimeEdge
	InitialExternalMilli int64
	InitialDirection     int
	Digest               string
}

type vSample struct {
	Sample   int
	External int64
}

type vAvalanche struct {
	Sample               int      `json:"sample"`
	Event                int      `json:"event"`
	Round                int      `json:"round"`
	Direction            int      `json:"direction"`
	TriggerExternalMilli int64    `json:"trigger_external_milli"`
	Flipped              []string `json:"flipped"`
	BeforeDigest         string   `json:"before_digest"`
	AfterDigest          string   `json:"after_digest"`
	EnergyBeforeMilli    int64    `json:"energy_before_milli"`
	EnergyAfterMilli     int64    `json:"energy_after_milli"`
}

type vCheckpointSpin struct {
	ID    string `json:"id"`
	State int    `json:"state"`
}

type vCheckpoint struct {
	Schema            string            `json:"schema"`
	ModelDigest       string            `json:"model_digest"`
	FieldDigest       string            `json:"field_digest"`
	NextSample        int               `json:"next_sample"`
	LastExternalMilli int64             `json:"last_external_milli"`
	LastDirection     int               `json:"last_direction"`
	Spins             []vCheckpointSpin `json:"spins"`
	ChainDigest       string            `json:"chain_digest"`
}

type vOutputs struct {
	Trajectory []byte
	Avalanches []byte
	Checkpoint []byte
}

func loadReferenceModel(path string) (vRuntimeModel, []int, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return vRuntimeModel{}, nil, err
	}
	var raw vModel
	if err := json.Unmarshal(data, &raw); err != nil {
		return vRuntimeModel{}, nil, err
	}
	spins := append([]vSpin(nil), raw.Spins...)
	sort.Slice(spins, func(i, j int) bool { return spins[i].ID < spins[j].ID })
	index := make(map[string]int, len(spins))
	states := make([]int, len(spins))
	var canonical strings.Builder
	for i, spin := range spins {
		index[spin.ID] = i
		states[i] = spin.Initial
		fmt.Fprintf(&canonical, "spin\t%s\t%d\t%d\n", spin.ID, spin.BiasMilli, spin.Initial)
	}
	type named struct {
		a, b string
		j    int64
	}
	namedEdges := make([]named, 0, len(raw.Edges))
	for _, edge := range raw.Edges {
		a, b := edge.A, edge.B
		if b < a {
			a, b = b, a
		}
		namedEdges = append(namedEdges, named{a: a, b: b, j: edge.CouplingMilli})
	}
	sort.Slice(namedEdges, func(i, j int) bool {
		if namedEdges[i].a != namedEdges[j].a {
			return namedEdges[i].a < namedEdges[j].a
		}
		return namedEdges[i].b < namedEdges[j].b
	})
	edges := make([]vRuntimeEdge, len(namedEdges))
	for i, edge := range namedEdges {
		edges[i] = vRuntimeEdge{A: index[edge.a], B: index[edge.b], J: edge.j}
		fmt.Fprintf(&canonical, "edge\t%s\t%s\t%d\n", edge.a, edge.b, edge.j)
	}
	sum := sha256.Sum256([]byte(canonical.String()))
	return vRuntimeModel{
		Spins:                spins,
		Edges:                edges,
		InitialExternalMilli: raw.InitialExternalMilli,
		InitialDirection:     raw.InitialDirection,
		Digest:               hex.EncodeToString(sum[:]),
	}, states, nil
}

func loadReferenceField(path string) ([]vSample, string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, "", err
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	if !scanner.Scan() || scanner.Text() != "sample\texternal_milli" {
		return nil, "", fmt.Errorf("invalid field header")
	}
	var canonical strings.Builder
	canonical.WriteString("sample\texternal_milli\n")
	var samples []vSample
	for scanner.Scan() {
		parts := strings.Split(scanner.Text(), "\t")
		if len(parts) != 2 {
			return nil, "", fmt.Errorf("invalid field row")
		}
		n, err := strconv.Atoi(parts[0])
		if err != nil {
			return nil, "", err
		}
		h, err := strconv.ParseInt(parts[1], 10, 64)
		if err != nil {
			return nil, "", err
		}
		samples = append(samples, vSample{Sample: n, External: h})
		fmt.Fprintf(&canonical, "%d\t%d\n", n, h)
	}
	if err := scanner.Err(); err != nil {
		return nil, "", err
	}
	sum := sha256.Sum256([]byte(canonical.String()))
	return samples, hex.EncodeToString(sum[:]), nil
}

func refStateDigest(model vRuntimeModel, states []int) string {
	var b strings.Builder
	for i, spin := range model.Spins {
		fmt.Fprintf(&b, "%s\t%d\n", spin.ID, states[i])
	}
	sum := sha256.Sum256([]byte(b.String()))
	return hex.EncodeToString(sum[:])
}

func refEnergy(model vRuntimeModel, states []int, external int64) int64 {
	var magnetization, bias, coupling int64
	for i, spin := range model.Spins {
		magnetization += int64(states[i])
		bias += spin.BiasMilli * int64(states[i])
	}
	for _, edge := range model.Edges {
		coupling += edge.J * int64(states[edge.A]*states[edge.B])
	}
	return -external*magnetization - bias - coupling
}

func refMagnetization(states []int) int {
	total := 0
	for _, state := range states {
		total += state
	}
	return total
}

func refForces(model vRuntimeModel, states []int, external int64) []int64 {
	forces := make([]int64, len(model.Spins))
	for i, spin := range model.Spins {
		forces[i] = external + spin.BiasMilli
	}
	for _, edge := range model.Edges {
		forces[edge.A] += edge.J * int64(states[edge.B])
		forces[edge.B] += edge.J * int64(states[edge.A])
	}
	return forces
}

func refTrigger(model vRuntimeModel, states []int, current, target int64, direction int) (int64, bool) {
	forces := refForces(model, states, current)
	for i, state := range states {
		if direction == 1 && state == -1 && forces[i] >= 0 {
			return current, true
		}
		if direction == -1 && state == 1 && forces[i] <= 0 {
			return current, true
		}
	}
	found := false
	var best int64
	for i, spin := range model.Spins {
		if (direction == 1 && states[i] != -1) || (direction == -1 && states[i] != 1) {
			continue
		}
		neighbor := int64(0)
		for _, edge := range model.Edges {
			if edge.A == i {
				neighbor += edge.J * int64(states[edge.B])
			} else if edge.B == i {
				neighbor += edge.J * int64(states[edge.A])
			}
		}
		threshold := -spin.BiasMilli - neighbor
		if direction == 1 && threshold > current && threshold <= target && (!found || threshold < best) {
			best, found = threshold, true
		}
		if direction == -1 && threshold < current && threshold >= target && (!found || threshold > best) {
			best, found = threshold, true
		}
	}
	return best, found
}

func refStabilize(model vRuntimeModel, states []int, sample, event int, trigger int64, direction int) []vAvalanche {
	var out []vAvalanche
	for round := 1; ; round++ {
		forces := refForces(model, states, trigger)
		var eligible []int
		for i, state := range states {
			if direction == 1 && state == -1 && forces[i] >= 0 {
				eligible = append(eligible, i)
			}
			if direction == -1 && state == 1 && forces[i] <= 0 {
				eligible = append(eligible, i)
			}
		}
		if len(eligible) == 0 {
			break
		}
		beforeDigest := refStateDigest(model, states)
		beforeEnergy := refEnergy(model, states, trigger)
		flipped := make([]string, len(eligible))
		for k, i := range eligible {
			states[i] = -states[i]
			flipped[k] = model.Spins[i].ID
		}
		out = append(out, vAvalanche{
			Sample: sample, Event: event, Round: round, Direction: direction,
			TriggerExternalMilli: trigger, Flipped: flipped,
			BeforeDigest: beforeDigest, AfterDigest: refStateDigest(model, states),
			EnergyBeforeMilli: beforeEnergy, EnergyAfterMilli: refEnergy(model, states, trigger),
		})
	}
	return out
}

func refTraverse(model vRuntimeModel, states []int, sample int, start, target int64, direction int) []vAvalanche {
	current := start
	var out []vAvalanche
	for event := 1; ; event++ {
		trigger, ok := refTrigger(model, states, current, target, direction)
		if !ok {
			break
		}
		rounds := refStabilize(model, states, sample, event, trigger, direction)
		if len(rounds) == 0 {
			break
		}
		out = append(out, rounds...)
		current = trigger
	}
	return out
}

func refDirection(target, previous int64, previousDirection int) int {
	if target > previous {
		return 1
	}
	if target < previous {
		return -1
	}
	return previousDirection
}

func expectedRun(modelPath, fieldPath string, start *vCheckpoint, stopAfter int) (vOutputs, error) {
	model, states, err := loadReferenceModel(modelPath)
	if err != nil {
		return vOutputs{}, err
	}
	field, fieldDigest, err := loadReferenceField(fieldPath)
	if err != nil {
		return vOutputs{}, err
	}
	next := 0
	previousExternal := model.InitialExternalMilli
	previousDirection := model.InitialDirection
	previousChain := strings.Repeat("0", 64)
	if start != nil {
		next = start.NextSample
		previousExternal = start.LastExternalMilli
		previousDirection = start.LastDirection
		previousChain = start.ChainDigest
		states = make([]int, len(start.Spins))
		for i, spin := range start.Spins {
			states[i] = spin.State
		}
	}
	end := len(field)
	if stopAfter > 0 && next+stopAfter < end {
		end = next + stopAfter
	}
	var trajectory strings.Builder
	trajectory.WriteString("sample\texternal_milli\tdirection\tavalanche_events\tavalanche_rounds\tflipped_total\tmagnetization_sum\tenergy_milli\tstate_digest\tchain_digest\n")
	var avalanches []byte
	for i := next; i < end; i++ {
		sample := field[i]
		direction := refDirection(sample.External, previousExternal, previousDirection)
		records := refTraverse(model, states, sample.Sample, previousExternal, sample.External, direction)
		var sampleBytes []byte
		flippedTotal := 0
		events, lastEvent := 0, 0
		for _, record := range records {
			line, _ := json.Marshal(record)
			sampleBytes = append(sampleBytes, line...)
			sampleBytes = append(sampleBytes, '\n')
			flippedTotal += len(record.Flipped)
			if record.Event != lastEvent {
				events++
				lastEvent = record.Event
			}
		}
		avalanches = append(avalanches, sampleBytes...)
		stateDigest := refStateDigest(model, states)
		prefix := fmt.Sprintf("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t",
			sample.Sample, sample.External, direction, events, len(records), flippedTotal,
			refMagnetization(states), refEnergy(model, states, sample.External), stateDigest)
		h := sha256.New()
		h.Write([]byte(previousChain))
		h.Write([]byte("\n"))
		h.Write(sampleBytes)
		h.Write([]byte(prefix))
		h.Write([]byte("\n"))
		previousChain = hex.EncodeToString(h.Sum(nil))
		trajectory.WriteString(prefix + previousChain + "\n")
		previousExternal = sample.External
		previousDirection = direction
	}
	checkpointSpins := make([]vCheckpointSpin, len(model.Spins))
	for i, spin := range model.Spins {
		checkpointSpins[i] = vCheckpointSpin{ID: spin.ID, State: states[i]}
	}
	cp := vCheckpoint{
		Schema: "rfim-checkpoint-v2", ModelDigest: model.Digest, FieldDigest: fieldDigest,
		NextSample: end, LastExternalMilli: previousExternal, LastDirection: previousDirection,
		Spins: checkpointSpins, ChainDigest: previousChain,
	}
	cpBytes, _ := json.MarshalIndent(cp, "", "  ")
	cpBytes = append(cpBytes, '\n')
	return vOutputs{Trajectory: []byte(trajectory.String()), Avalanches: avalanches, Checkpoint: cpBytes}, nil
}

func readOutputs(dir string) (vOutputs, error) {
	trajectory, err := os.ReadFile(dir + "/trajectory.tsv")
	if err != nil {
		return vOutputs{}, err
	}
	avalanches, err := os.ReadFile(dir + "/avalanches.jsonl")
	if err != nil {
		return vOutputs{}, err
	}
	checkpoint, err := os.ReadFile(dir + "/checkpoint.json")
	if err != nil {
		return vOutputs{}, err
	}
	return vOutputs{Trajectory: trajectory, Avalanches: avalanches, Checkpoint: checkpoint}, nil
}

func assertBytes(label string, got, want []byte) error {
	if bytes.Equal(got, want) {
		return nil
	}
	return fmt.Errorf("%s mismatch\nwant: %q\n got: %q", label, want, got)
}
