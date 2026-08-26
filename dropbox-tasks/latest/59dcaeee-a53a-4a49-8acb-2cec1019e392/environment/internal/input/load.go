package input

import (
	"bufio"
	"bytes"
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"regexp"
	"sort"
	"strconv"
	"strings"

	"rfimhyst/internal/contract"
)

var idPattern = regexp.MustCompile(`^[A-Za-z0-9._-]+$`)

func decodeStrictBytes(data []byte, dst any) error {
	dec := json.NewDecoder(bytes.NewReader(data))
	dec.DisallowUnknownFields()
	if err := dec.Decode(dst); err != nil {
		return err
	}
	if err := dec.Decode(&struct{}{}); !errors.Is(err, io.EOF) {
		if err == nil {
			return fmt.Errorf("multiple JSON values")
		}
		return err
	}
	return nil
}

func decodeStrict(path string, dst any) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return decodeStrictBytes(data, dst)
}

func LoadModel(path string) (*contract.RuntimeModel, []int, error) {
	var raw contract.Model
	if err := decodeStrict(path, &raw); err != nil {
		return nil, nil, fmt.Errorf("model: %w", err)
	}
	if raw.Schema != "rfim-v1" {
		return nil, nil, fmt.Errorf("model schema must be rfim-v1")
	}
	if raw.InitialDirection != -1 && raw.InitialDirection != 1 {
		return nil, nil, fmt.Errorf("initial_direction must be -1 or 1")
	}
	if len(raw.Spins) == 0 {
		return nil, nil, fmt.Errorf("model must contain at least one spin")
	}
	spins := append([]contract.Spin(nil), raw.Spins...)
	sort.Slice(spins, func(i, j int) bool { return spins[i].ID < spins[j].ID })
	index := make(map[string]int, len(spins))
	states := make([]int, len(spins))
	for i, spin := range spins {
		if !idPattern.MatchString(spin.ID) {
			return nil, nil, fmt.Errorf("invalid spin id %q", spin.ID)
		}
		if i > 0 && spins[i-1].ID == spin.ID {
			return nil, nil, fmt.Errorf("duplicate spin id %q", spin.ID)
		}
		if spin.Initial != -1 && spin.Initial != 1 {
			return nil, nil, fmt.Errorf("spin %q initial must be -1 or 1", spin.ID)
		}
		index[spin.ID] = i
		states[i] = spin.Initial
	}
	type namedEdge struct {
		a, b string
		j    int64
	}
	named := make([]namedEdge, 0, len(raw.Edges))
	seen := map[string]bool{}
	for _, edge := range raw.Edges {
		if edge.A == edge.B {
			return nil, nil, fmt.Errorf("self edge %q", edge.A)
		}
		if edge.CouplingMilli < 0 {
			return nil, nil, fmt.Errorf("edge coupling must be non-negative")
		}
		if _, ok := index[edge.A]; !ok {
			return nil, nil, fmt.Errorf("edge endpoint %q is unknown", edge.A)
		}
		if _, ok := index[edge.B]; !ok {
			return nil, nil, fmt.Errorf("edge endpoint %q is unknown", edge.B)
		}
		a, b := edge.A, edge.B
		if b < a {
			a, b = b, a
		}
		key := a + "\x00" + b
		if seen[key] {
			return nil, nil, fmt.Errorf("duplicate edge %q-%q", a, b)
		}
		seen[key] = true
		named = append(named, namedEdge{a: a, b: b, j: edge.CouplingMilli})
	}
	sort.Slice(named, func(i, j int) bool {
		if named[i].a != named[j].a {
			return named[i].a < named[j].a
		}
		return named[i].b < named[j].b
	})
	edges := make([]contract.RuntimeEdge, len(named))
	var canonical strings.Builder
	for _, spin := range spins {
		fmt.Fprintf(&canonical, "spin\t%s\t%d\t%d\n", spin.ID, spin.BiasMilli, spin.Initial)
	}
	for i, edge := range named {
		edges[i] = contract.RuntimeEdge{A: index[edge.a], B: index[edge.b], CouplingMilli: edge.j}
		fmt.Fprintf(&canonical, "edge\t%s\t%s\t%d\n", edge.a, edge.b, edge.j)
	}
	sum := sha256.Sum256([]byte(canonical.String()))
	return &contract.RuntimeModel{
		Spins:                spins,
		Edges:                edges,
		InitialExternalMilli: raw.InitialExternalMilli,
		InitialDirection:     raw.InitialDirection,
		Digest:               hex.EncodeToString(sum[:]),
	}, states, nil
}

func LoadField(path string) ([]contract.FieldSample, string, error) {
	file, err := os.Open(path)
	if err != nil {
		return nil, "", fmt.Errorf("field: %w", err)
	}
	defer file.Close()
	scanner := bufio.NewScanner(file)
	if !scanner.Scan() || scanner.Text() != "sample\texternal_milli" {
		return nil, "", fmt.Errorf("field header must be sample\\texternal_milli")
	}
	var canonical strings.Builder
	canonical.WriteString("sample\texternal_milli\n")
	var out []contract.FieldSample
	lineNo := 1
	for scanner.Scan() {
		lineNo++
		line := scanner.Text()
		parts := strings.Split(line, "\t")
		if len(parts) != 2 {
			return nil, "", fmt.Errorf("field line %d must contain two tab-separated columns", lineNo)
		}
		sample, err := strconv.Atoi(parts[0])
		if err != nil || sample != len(out) {
			return nil, "", fmt.Errorf("field line %d sample must equal %d", lineNo, len(out))
		}
		external, err := strconv.ParseInt(parts[1], 10, 64)
		if err != nil {
			return nil, "", fmt.Errorf("field line %d external_milli is invalid", lineNo)
		}
		out = append(out, contract.FieldSample{Sample: sample, ExternalMilli: external})
		fmt.Fprintf(&canonical, "%d\t%d\n", sample, external)
	}
	if err := scanner.Err(); err != nil {
		return nil, "", fmt.Errorf("field: %w", err)
	}
	if len(out) == 0 {
		return nil, "", fmt.Errorf("field must contain at least one sample")
	}
	var digestInput strings.Builder
	digestInput.WriteString("sample\texternal_milli\n")
	for i := 0; i+1 < len(out); i++ {
		fmt.Fprintf(&digestInput, "%d\t%d\n", out[i].Sample, out[i].ExternalMilli)
	}
	sum := sha256.Sum256([]byte(digestInput.String()))
	return out, hex.EncodeToString(sum[:]), nil
}

func LoadCheckpoint(path string) (*contract.Checkpoint, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("checkpoint: %w", err)
	}
	var members map[string]json.RawMessage
	if err := json.Unmarshal(data, &members); err != nil {
		return nil, fmt.Errorf("checkpoint: %w", err)
	}
	expected := []string{"schema", "model_digest", "field_digest", "next_sample", "last_external_milli", "last_direction", "spins", "chain_digest"}
	if len(members) != len(expected) {
		return nil, fmt.Errorf("checkpoint must contain exactly the documented keys")
	}
	for _, key := range expected {
		if _, ok := members[key]; !ok {
			return nil, fmt.Errorf("checkpoint is missing key %q", key)
		}
	}
	var cp contract.Checkpoint
	if err := decodeStrictBytes(data, &cp); err != nil {
		return nil, fmt.Errorf("checkpoint: %w", err)
	}
	return &cp, nil
}
