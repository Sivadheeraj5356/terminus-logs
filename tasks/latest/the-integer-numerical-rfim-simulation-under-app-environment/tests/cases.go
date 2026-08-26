package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
)

func writeStudy(root, stem, model, field string) (string, string, error) {
	modelPath := filepath.Join(root, stem+"-model.json")
	fieldPath := filepath.Join(root, stem+"-field.tsv")
	if err := os.WriteFile(modelPath, []byte(model), 0o644); err != nil {
		return "", "", err
	}
	if err := os.WriteFile(fieldPath, []byte(field), 0o644); err != nil {
		return "", "", err
	}
	return modelPath, fieldPath, nil
}

func parseExtra(extra []string) (*vCheckpoint, int, error) {
	var start *vCheckpoint
	stopAfter := 0
	for i := 0; i < len(extra); i++ {
		switch extra[i] {
		case "--resume":
			if i+1 >= len(extra) {
				return nil, 0, fmt.Errorf("missing resume path")
			}
			data, err := os.ReadFile(extra[i+1])
			if err != nil {
				return nil, 0, err
			}
			var cp vCheckpoint
			if err := json.Unmarshal(data, &cp); err != nil {
				return nil, 0, err
			}
			start = &cp
			i++
		case "--stop-after":
			if i+1 >= len(extra) {
				return nil, 0, fmt.Errorf("missing stop value")
			}
			if _, err := fmt.Sscanf(extra[i+1], "%d", &stopAfter); err != nil {
				return nil, 0, err
			}
			i++
		}
	}
	return start, stopAfter, nil
}

func compareRun(binary, modelPath, fieldPath, out string, extra ...string) error {
	start, stopAfter, err := parseExtra(extra)
	if err != nil {
		return err
	}
	args := []string{"--model", modelPath, "--field", fieldPath, "--output-dir", out}
	args = append(args, extra...)
	result := runCommand(binary, args...)
	if result.Code != 0 {
		return fmt.Errorf("program exited %d: %s", result.Code, result.Stderr)
	}
	got, err := readOutputs(out)
	if err != nil {
		return err
	}
	want, err := expectedRun(modelPath, fieldPath, start, stopAfter)
	if err != nil {
		return err
	}
	if err := assertBytes("trajectory", got.Trajectory, want.Trajectory); err != nil {
		return err
	}
	if err := assertBytes("avalanches", got.Avalanches, want.Avalanches); err != nil {
		return err
	}
	return assertBytes("checkpoint", got.Checkpoint, want.Checkpoint)
}

func bundledCase(binary, appDir, root string) error {
	return compareRun(binary,
		filepath.Join(appDir, "fixtures", "model.json"),
		filepath.Join(appDir, "fixtures", "field.tsv"),
		filepath.Join(root, "bundled"))
}

func multiEventTieCase(binary, root string) error {
	model := `{
  "schema":"rfim-v1",
  "initial_external_milli":-300,
  "initial_direction":1,
  "spins":[
    {"id":"e","bias_milli":-180,"initial":-1},
    {"id":"d","bias_milli":-120,"initial":-1},
    {"id":"b","bias_milli":-100,"initial":-1},
    {"id":"a","bias_milli":50,"initial":-1},
    {"id":"c","bias_milli":-120,"initial":-1}
  ],
  "edges":[{"a":"b","b":"a","coupling_milli":100}]
}`
	field := "sample\texternal_milli\n0\t220\n1\t220\n2\t-220\n3\t150\n"
	modelPath, fieldPath, err := writeStudy(root, "multi", model, field)
	if err != nil {
		return err
	}
	out := filepath.Join(root, "multi-out")
	if err := compareRun(binary, modelPath, fieldPath, out); err != nil {
		return err
	}
	data, err := os.ReadFile(filepath.Join(out, "avalanches.jsonl"))
	if err != nil {
		return err
	}
	lines := bytes.Split(bytes.TrimSpace(data), []byte("\n"))
	var sampleZero []vAvalanche
	for _, line := range lines {
		var record vAvalanche
		if err := json.Unmarshal(line, &record); err != nil {
			return err
		}
		if record.Sample == 0 {
			sampleZero = append(sampleZero, record)
		}
	}
	if len(sampleZero) != 4 {
		return fmt.Errorf("expected four rounds in first interval, got %d", len(sampleZero))
	}
	if sampleZero[0].Event != 1 || sampleZero[0].TriggerExternalMilli != 50 || sampleZero[1].Round != 2 {
		return fmt.Errorf("cooperative first event was not preserved: %+v", sampleZero[:2])
	}
	if sampleZero[2].Event != 2 || sampleZero[2].TriggerExternalMilli != 120 || strings.Join(sampleZero[2].Flipped, ",") != "c,d" {
		return fmt.Errorf("threshold tie was not grouped: %+v", sampleZero[2])
	}
	if sampleZero[3].Event != 3 || sampleZero[3].TriggerExternalMilli != 180 {
		return fmt.Errorf("third event trigger mismatch: %+v", sampleZero[3])
	}
	return nil
}

func currentFieldEligibilityCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":0,"initial_direction":1,"spins":[{"id":"a","bias_milli":10,"initial":-1},{"id":"b","bias_milli":10,"initial":-1}],"edges":[]}`
	field := "sample\texternal_milli\n0\t0\n1\t0\n2\t-20\n"
	modelPath, fieldPath, err := writeStudy(root, "current", model, field)
	if err != nil {
		return err
	}
	out := filepath.Join(root, "current-out")
	if err := compareRun(binary, modelPath, fieldPath, out); err != nil {
		return err
	}
	data, _ := os.ReadFile(filepath.Join(out, "avalanches.jsonl"))
	var first vAvalanche
	if err := json.Unmarshal(bytes.Split(data, []byte("\n"))[0], &first); err != nil {
		return err
	}
	if first.Sample != 0 || first.TriggerExternalMilli != 0 || strings.Join(first.Flipped, ",") != "a,b" {
		return fmt.Errorf("current-field eligibility mismatch: %+v", first)
	}
	return nil
}

func shuffledCase(binary, root string) error {
	base := vModel{
		Schema: "rfim-v1", InitialExternalMilli: -300, InitialDirection: 1,
		Spins: []vSpin{{ID: "a", BiasMilli: 50, Initial: -1}, {ID: "b", BiasMilli: -100, Initial: -1}, {ID: "c", BiasMilli: -120, Initial: -1}},
		Edges: []vEdge{{A: "a", B: "b", CouplingMilli: 100}},
	}
	shuffled := base
	shuffled.Spins = []vSpin{base.Spins[2], base.Spins[0], base.Spins[1]}
	shuffled.Edges = []vEdge{{A: "b", B: "a", CouplingMilli: 100}}
	one, _ := json.Marshal(base)
	two, _ := json.Marshal(shuffled)
	field := "sample\texternal_milli\n0\t200\n1\t-200\n"
	m1, f, err := writeStudy(root, "ordered", string(one), field)
	if err != nil {
		return err
	}
	m2 := filepath.Join(root, "shuffled-model.json")
	if err := os.WriteFile(m2, two, 0o644); err != nil {
		return err
	}
	o1, o2 := filepath.Join(root, "order-one"), filepath.Join(root, "order-two")
	if err := compareRun(binary, m1, f, o1); err != nil {
		return err
	}
	if err := compareRun(binary, m2, f, o2); err != nil {
		return err
	}
	first, _ := readOutputs(o1)
	second, _ := readOutputs(o2)
	if err := assertBytes("shuffled trajectory", second.Trajectory, first.Trajectory); err != nil {
		return err
	}
	if err := assertBytes("shuffled avalanches", second.Avalanches, first.Avalanches); err != nil {
		return err
	}
	return assertBytes("shuffled checkpoint", second.Checkpoint, first.Checkpoint)
}

func splitSameDirectoryCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":-300,"initial_direction":1,"spins":[{"id":"a","bias_milli":50,"initial":-1},{"id":"b","bias_milli":-100,"initial":-1},{"id":"c","bias_milli":-120,"initial":-1},{"id":"d","bias_milli":-180,"initial":-1}],"edges":[{"a":"a","b":"b","coupling_milli":100}]}`
	field := "sample\texternal_milli\n0\t150\n1\t80\n2\t150\n3\t-220\n4\t200\n5\t200\n"
	modelPath, fieldPath, err := writeStudy(root, "split", model, field)
	if err != nil {
		return err
	}
	fullDir := filepath.Join(root, "split-full")
	if err := compareRun(binary, modelPath, fieldPath, fullDir); err != nil {
		return err
	}
	partDir := filepath.Join(root, "split-same")
	if err := compareRun(binary, modelPath, fieldPath, partDir, "--stop-after", "2"); err != nil {
		return err
	}
	one, _ := readOutputs(partDir)
	checkpoint := filepath.Join(partDir, "checkpoint.json")
	if err := compareRun(binary, modelPath, fieldPath, partDir, "--resume", checkpoint, "--stop-after", "2"); err != nil {
		return err
	}
	two, _ := readOutputs(partDir)
	if err := compareRun(binary, modelPath, fieldPath, partDir, "--resume", checkpoint); err != nil {
		return err
	}
	three, _ := readOutputs(partDir)
	full, _ := readOutputs(fullDir)
	headerEnd := bytes.IndexByte(one.Trajectory, '\n') + 1
	combinedTrajectory := append([]byte{}, one.Trajectory...)
	combinedTrajectory = append(combinedTrajectory, two.Trajectory[headerEnd:]...)
	combinedTrajectory = append(combinedTrajectory, three.Trajectory[headerEnd:]...)
	if err := assertBytes("three-way trajectory", combinedTrajectory, full.Trajectory); err != nil {
		return err
	}
	combinedAvalanches := append([]byte{}, one.Avalanches...)
	combinedAvalanches = append(combinedAvalanches, two.Avalanches...)
	combinedAvalanches = append(combinedAvalanches, three.Avalanches...)
	if err := assertBytes("three-way avalanches", combinedAvalanches, full.Avalanches); err != nil {
		return err
	}
	return assertBytes("three-way checkpoint", three.Checkpoint, full.Checkpoint)
}

func fieldMutationRejectionCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":-100,"initial_direction":1,"spins":[{"id":"a","bias_milli":0,"initial":-1}],"edges":[]}`
	field := "sample\texternal_milli\n0\t0\n1\t100\n2\t-100\n"
	modelPath, fieldPath, err := writeStudy(root, "field-bind", model, field)
	if err != nil {
		return err
	}
	first := filepath.Join(root, "field-bind-first")
	if err := compareRun(binary, modelPath, fieldPath, first, "--stop-after", "1"); err != nil {
		return err
	}
	checkpoint := filepath.Join(first, "checkpoint.json")
	mutations := []string{
		"sample\texternal_milli\n0\t1\n1\t100\n2\t-100\n",
		"sample\texternal_milli\n0\t0\n1\t100\n2\t-99\n",
	}
	for i, mutation := range mutations {
		mutatedPath := filepath.Join(root, fmt.Sprintf("mutated-field-%d.tsv", i))
		os.WriteFile(mutatedPath, []byte(mutation), 0o644)
		out := filepath.Join(root, fmt.Sprintf("mutated-out-%d", i))
		os.MkdirAll(out, 0o755)
		for _, name := range []string{"trajectory.tsv", "avalanches.jsonl", "checkpoint.json", ".trajectory.tsv.tmp"} {
			os.WriteFile(filepath.Join(out, name), []byte("stale"), 0o644)
		}
		result := runCommand(binary, "--model", modelPath, "--field", mutatedPath, "--output-dir", out, "--resume", checkpoint)
		if result.Code != 2 || !strings.Contains(result.Stderr, "field_digest") {
			return fmt.Errorf("field mutation %d was not rejected correctly: code=%d stderr=%q", i, result.Code, result.Stderr)
		}
		for _, name := range []string{"trajectory.tsv", "avalanches.jsonl", "checkpoint.json", ".trajectory.tsv.tmp"} {
			if _, err := os.Stat(filepath.Join(out, name)); !os.IsNotExist(err) {
				return fmt.Errorf("stale %s survived field mutation failure", name)
			}
		}
	}
	return nil
}

func returnPointMemoryCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":-300,"initial_direction":1,"spins":[{"id":"a","bias_milli":50,"initial":-1},{"id":"b","bias_milli":-100,"initial":-1},{"id":"c","bias_milli":-120,"initial":-1},{"id":"d","bias_milli":-180,"initial":-1}],"edges":[{"a":"a","b":"b","coupling_milli":100}]}`
	field := "sample\texternal_milli\n0\t150\n1\t80\n2\t150\n"
	modelPath, fieldPath, err := writeStudy(root, "rpm", model, field)
	if err != nil {
		return err
	}
	out := filepath.Join(root, "rpm-out")
	if err := compareRun(binary, modelPath, fieldPath, out); err != nil {
		return err
	}
	rows := strings.Split(strings.TrimSpace(string(mustRead(filepath.Join(out, "trajectory.tsv")))), "\n")
	if len(rows) != 4 {
		return fmt.Errorf("unexpected trajectory row count")
	}
	first := strings.Split(rows[1], "\t")
	returned := strings.Split(rows[3], "\t")
	if first[8] != returned[8] {
		return fmt.Errorf("return-point state digest mismatch: %s != %s", first[8], returned[8])
	}
	return nil
}

func mustRead(path string) []byte {
	data, err := os.ReadFile(path)
	if err != nil {
		panic(err)
	}
	return data
}

func deterministicAlternateRootCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":-200,"initial_direction":1,"spins":[{"id":"x","bias_milli":0,"initial":-1},{"id":"y","bias_milli":30,"initial":-1}],"edges":[{"a":"x","b":"y","coupling_milli":60}]}`
	field := "sample\texternal_milli\n0\t100\n1\t-100\n2\t100\n"
	modelPath, fieldPath, err := writeStudy(root, "det", model, field)
	if err != nil {
		return err
	}
	a, b := filepath.Join(root, "a", "deep", "out"), filepath.Join(root, "b", "out")
	if err := compareRun(binary, modelPath, fieldPath, a); err != nil {
		return err
	}
	if err := compareRun(binary, modelPath, fieldPath, b); err != nil {
		return err
	}
	one, _ := readOutputs(a)
	two, _ := readOutputs(b)
	if err := assertBytes("alternate trajectory", two.Trajectory, one.Trajectory); err != nil {
		return err
	}
	if err := assertBytes("alternate avalanches", two.Avalanches, one.Avalanches); err != nil {
		return err
	}
	return assertBytes("alternate checkpoint", two.Checkpoint, one.Checkpoint)
}

func invalidCleanupCase(binary, root string) error {
	out := filepath.Join(root, "invalid-out")
	os.MkdirAll(out, 0o755)
	for _, name := range []string{"trajectory.tsv", "avalanches.jsonl", "checkpoint.json", ".checkpoint.json.tmp"} {
		os.WriteFile(filepath.Join(out, name), []byte("stale"), 0o644)
	}
	model := `{"schema":"rfim-v1","initial_external_milli":0,"initial_direction":1,"spins":[{"id":"a","bias_milli":0,"initial":-1},{"id":"b","bias_milli":0,"initial":-1}],"edges":[{"a":"a","b":"b","coupling_milli":1},{"a":"b","b":"a","coupling_milli":1}]}`
	field := "sample\texternal_milli\n0\t0\n"
	modelPath, fieldPath, err := writeStudy(root, "invalid", model, field)
	if err != nil {
		return err
	}
	result := runCommand(binary, "--model", modelPath, "--field", fieldPath, "--output-dir", out)
	if result.Code != 2 || !strings.HasPrefix(result.Stderr, "rfimhyst: input error:") {
		return fmt.Errorf("invalid input exit mismatch: code=%d stderr=%q", result.Code, result.Stderr)
	}
	for _, name := range []string{"trajectory.tsv", "avalanches.jsonl", "checkpoint.json", ".checkpoint.json.tmp"} {
		if _, err := os.Stat(filepath.Join(out, name)); !os.IsNotExist(err) {
			return fmt.Errorf("stale %s survived invalid input", name)
		}
	}
	return nil
}

func completeResumeCase(binary, root string) error {
	model := `{"schema":"rfim-v1","initial_external_milli":-10,"initial_direction":1,"spins":[{"id":"a","bias_milli":0,"initial":-1}],"edges":[]}`
	field := "sample\texternal_milli\n0\t0\n"
	modelPath, fieldPath, err := writeStudy(root, "complete", model, field)
	if err != nil {
		return err
	}
	first, second := filepath.Join(root, "complete-first"), filepath.Join(root, "complete-second")
	if err := compareRun(binary, modelPath, fieldPath, first); err != nil {
		return err
	}
	if err := compareRun(binary, modelPath, fieldPath, second, "--resume", filepath.Join(first, "checkpoint.json")); err != nil {
		return err
	}
	outputs, _ := readOutputs(second)
	if len(outputs.Avalanches) != 0 || bytes.Count(outputs.Trajectory, []byte("\n")) != 1 {
		return fmt.Errorf("completed continuation must emit header-only trajectory and empty avalanche log")
	}
	return nil
}
