package session

import (
	"crypto/sha256"
	"encoding/hex"
	"flag"
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"

	"rfimhyst/dyn"
	"rfimhyst/ham"
	"rfimhyst/internal/artifact"
	"rfimhyst/internal/contract"
	"rfimhyst/internal/input"
)

const zeroChain = "0000000000000000000000000000000000000000000000000000000000000000"

var hexDigest = regexp.MustCompile(`^[0-9a-f]{64}$`)

func directionFor(target, previous int64, previousDirection int) int {
	if target > previous {
		return 1
	}
	if target < previous {
		return -1
	}
	return previousDirection
}

func validateCheckpoint(cp *contract.Checkpoint, model *contract.RuntimeModel, field []contract.FieldSample, fieldDigest string) ([]int, error) {
	if cp.Schema != "rfim-checkpoint-v2" {
		return nil, fmt.Errorf("checkpoint schema must be rfim-checkpoint-v2")
	}
	if cp.ModelDigest != model.Digest {
		return nil, fmt.Errorf("checkpoint model_digest does not match model")
	}
	if cp.NextSample < 0 || cp.NextSample > len(field) {
		return nil, fmt.Errorf("checkpoint next_sample is out of range")
	}
	if cp.LastDirection != -1 && cp.LastDirection != 1 {
		return nil, fmt.Errorf("checkpoint last_direction must be -1 or 1")
	}
	if !hexDigest.MatchString(cp.ChainDigest) {
		return nil, fmt.Errorf("checkpoint chain_digest must be lowercase SHA-256 hex")
	}
	expectedExternal := model.InitialExternalMilli
	if cp.NextSample > 0 {
		expectedExternal = field[cp.NextSample-1].ExternalMilli
	}
	if cp.LastExternalMilli != expectedExternal {
		return nil, fmt.Errorf("checkpoint last_external_milli does not match field history")
	}
	if len(cp.Spins) != len(model.Spins) {
		return nil, fmt.Errorf("checkpoint spin count does not match model")
	}
	states := make([]int, len(model.Spins))
	for i, spin := range cp.Spins {
		if spin.ID != model.Spins[i].ID {
			return nil, fmt.Errorf("checkpoint spins must be sorted and match model ids")
		}
		if spin.State != -1 && spin.State != 1 {
			return nil, fmt.Errorf("checkpoint spin state must be -1 or 1")
		}
		states[i] = spin.State
	}
	return states, nil
}

func processStudy(args []string) error {
	flags := flag.NewFlagSet("rfimhyst", flag.ContinueOnError)
	flags.SetOutput(os.Stderr)
	modelPath := flags.String("model", "", "model JSON path")
	fieldPath := flags.String("field", "", "field TSV path")
	outputDir := flags.String("output-dir", "/app/output", "output directory")
	resumePath := flags.String("resume", "", "checkpoint path")
	stopAfter := flags.Int("stop-after", 0, "maximum samples to process in this invocation")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected positional arguments")
	}
	if *modelPath == "" || *fieldPath == "" {
		return fmt.Errorf("--model and --field are required")
	}
	if *stopAfter < 0 {
		return fmt.Errorf("--stop-after must be non-negative")
	}
	artifact.Cleanup(*outputDir)
	model, initialStates, err := input.LoadModel(*modelPath)
	if err != nil {
		return err
	}
	field, fieldDigest, err := input.LoadField(*fieldPath)
	if err != nil {
		return err
	}
	states := initialStates
	nextSample := 0
	previousExternal := model.InitialExternalMilli
	previousDirection := model.InitialDirection
	previousChain := zeroChain
	if *resumePath != "" {
		cp, err := input.LoadCheckpoint(*resumePath)
		if err != nil {
			return err
		}
		states, err = validateCheckpoint(cp, model, field, fieldDigest)
		if err != nil {
			return err
		}
		nextSample = cp.NextSample
		previousExternal = cp.LastExternalMilli
		previousDirection = model.InitialDirection
		previousChain = zeroChain
	}

	end := len(field)
	if *stopAfter > 0 && nextSample+*stopAfter < end {
		end = nextSample + *stopAfter
	}
	var trajectory strings.Builder
	trajectory.WriteString("sample\texternal_milli\tdirection\tavalanche_events\tavalanche_rounds\tflipped_total\tmagnetization_sum\tenergy_milli\tstate_digest\tchain_digest\n")
	var avalancheBytes []byte
	for sampleIndex := nextSample; sampleIndex < end; sampleIndex++ {
		sample := field[sampleIndex]
		direction := directionFor(sample.ExternalMilli, previousExternal, previousDirection)
		records := dyn.Traverse(model, states, sample.Sample, previousExternal, sample.ExternalMilli, direction)
		sampleAvalanches := make([]byte, 0)
		flippedTotal := 0
		eventCount := 0
		lastEvent := 0
		for _, record := range records {
			line, err := artifact.AvalancheLine(record)
			if err != nil {
				return err
			}
			sampleAvalanches = append(sampleAvalanches, line...)
			flippedTotal += len(record.Flipped)
			if record.Event != lastEvent {
				eventCount++
				lastEvent = record.Event
			}
		}
		avalancheBytes = append(avalancheBytes, sampleAvalanches...)
		stateDigest := artifact.StateDigest(model, states)
		prefix := fmt.Sprintf("%d\t%d\t%d\t%d\t%d\t%d\t%d\t%d\t%s\t",
			sample.Sample,
			sample.ExternalMilli,
			direction,
			eventCount,
			len(records),
			flippedTotal,
			ham.MagnetizationSum(states),
			ham.EnergyMilli(model, states, sample.ExternalMilli),
			stateDigest,
		)
		hasher := sha256.New()
		hasher.Write([]byte(previousChain))
		hasher.Write([]byte("\n"))
		hasher.Write([]byte(prefix))
		hasher.Write([]byte("\n"))
		previousChain = hex.EncodeToString(hasher.Sum(nil))
		trajectory.WriteString(prefix)
		trajectory.WriteString(previousChain)
		trajectory.WriteByte('\n')
		previousExternal = sample.ExternalMilli
		previousDirection = direction
	}
	checkpointSpins := make([]contract.CheckpointSpin, len(model.Spins))
	for i, spin := range model.Spins {
		checkpointSpins[i] = contract.CheckpointSpin{ID: spin.ID, State: states[i]}
	}
	checkpoint := contract.Checkpoint{
		Schema:            "rfim-checkpoint-v2",
		ModelDigest:       model.Digest,
		FieldDigest:       fieldDigest,
		NextSample:        end,
		LastExternalMilli: previousExternal,
		LastDirection:     previousDirection,
		Spins:             checkpointSpins,
		ChainDigest:       previousChain,
	}
	checkpointBytes, err := artifact.CheckpointBytes(checkpoint)
	if err != nil {
		return err
	}
	if err := artifact.AtomicWrite(*outputDir, []byte(trajectory.String()), avalancheBytes, checkpointBytes); err != nil {
		return err
	}
	return nil
}

func outputDirFromArgs(args []string) string {
	outputDir := "/app/output"
	for i := 0; i+1 < len(args); i++ {
		if args[i] == "--output-dir" {
			outputDir = args[i+1]
		}
	}
	return outputDir
}

func Main() int {
	args := os.Args[1:]
	outputDir := outputDirFromArgs(args)
	if err := processStudy(args); err != nil {
		_ = os.MkdirAll(outputDir, 0o755)
		artifact.Cleanup(outputDir)
		fmt.Fprintf(os.Stderr, "rfimhyst: input error: %v\n", err)
		return 2
	}
	return 0
}

func ArtifactPath(dir, name string) string {
	return filepath.Join(dir, name)
}
