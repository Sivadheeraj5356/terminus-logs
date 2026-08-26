package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/terminus/ai-workflow-runtime/internal/cache"
	"github.com/terminus/ai-workflow-runtime/internal/certificate"
	"github.com/terminus/ai-workflow-runtime/internal/checkpoint"
	"github.com/terminus/ai-workflow-runtime/internal/compiler"
	"github.com/terminus/ai-workflow-runtime/internal/dag"
	"github.com/terminus/ai-workflow-runtime/internal/executor"
	"github.com/terminus/ai-workflow-runtime/internal/journal"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/parser"
	"github.com/terminus/ai-workflow-runtime/internal/policy"
	"github.com/terminus/ai-workflow-runtime/internal/recovery"
	"github.com/terminus/ai-workflow-runtime/internal/replay"
	"github.com/terminus/ai-workflow-runtime/internal/scheduler"
	"github.com/terminus/ai-workflow-runtime/internal/state"
	"github.com/terminus/ai-workflow-runtime/internal/util"
	"github.com/terminus/ai-workflow-runtime/internal/verification"
)

func main() {
	if len(os.Args) < 2 {
		usage()
		os.Exit(2)
	}
	cmd := os.Args[1]
	root := env("RUNTIME_ROOT", env("TB3_APP_ROOT", "/app"))
	cfg := pathsFrom(root)

	must(os.MkdirAll(cfg.state, 0o755))
	must(os.MkdirAll(cfg.output, 0o755))
	must(os.MkdirAll(cfg.cache, 0o755))
	must(os.MkdirAll(cfg.checkpoints, 0o755))

	var err error
	switch cmd {
	case "parse":
		err = stageParse(cfg)
	case "compile":
		err = stageCompile(cfg)
	case "schedule":
		err = stageSchedule(cfg)
	case "execute":
		err = stageExecute(cfg, "")
	case "checkpoint":
		err = stageCheckpoint(cfg)
	case "recover":
		err = stageRecover(cfg)
	case "replay":
		err = stageReplay(cfg)
	case "verify":
		err = stageVerify(cfg)
	case "certificate":
		err = stageCertificate(cfg)
	case "run":
		err = runAll(cfg)
	case "fail-run":
		failNode := env("RUNTIME_FAIL_NODE", "train")
		err = runWithFailure(cfg, failNode)
	default:
		usage()
		os.Exit(2)
	}
	if err != nil {
		fmt.Fprintf(os.Stderr, "runtime %s: %v\n", cmd, err)
		os.Exit(1)
	}
}

func usage() {
	fmt.Fprintf(os.Stderr, "usage: runtime <parse|compile|schedule|execute|checkpoint|recover|replay|verify|certificate|run|fail-run>\n")
}

type paths struct {
	root, state, output, cache, checkpoints, workflow, policy, token string
}

func pathsFrom(root string) paths {
	return paths{
		root:        root,
		state:       env("RUNTIME_STATE_DIR", filepath.Join(root, "state")),
		output:      env("RUNTIME_OUTPUT_DIR", filepath.Join(root, "output")),
		cache:       env("RUNTIME_CACHE_DIR", filepath.Join(root, "cache")),
		checkpoints: env("RUNTIME_CHECKPOINT_DIR", filepath.Join(root, "state", "checkpoints")),
		workflow:    env("RUNTIME_WORKFLOW", filepath.Join(root, "testdata", "workflows", "ai_training.json")),
		policy:      env("RUNTIME_POLICY", filepath.Join(root, "configs", "policy.json")),
		token:       env("RUNTIME_TOKEN_FILE", filepath.Join(root, "configs", "hmac_signing_token.txt")),
	}
}

func runAll(cfg paths) error {
	if err := stageParse(cfg); err != nil {
		return err
	}
	if err := stageCompile(cfg); err != nil {
		return err
	}
	if err := stageSchedule(cfg); err != nil {
		return err
	}
	if err := stageExecute(cfg, ""); err != nil {
		return err
	}
	if err := stageCheckpoint(cfg); err != nil {
		return err
	}
	if err := stageRecover(cfg); err != nil {
		return err
	}
	if err := stageReplay(cfg); err != nil {
		return err
	}
	if err := stageVerify(cfg); err != nil {
		return err
	}
	return stageCertificate(cfg)
}

func runWithFailure(cfg paths, failNode string) error {
	if err := stageParse(cfg); err != nil {
		return err
	}
	if err := stageCompile(cfg); err != nil {
		return err
	}
	if err := stageSchedule(cfg); err != nil {
		return err
	}
	if err := stageExecute(cfg, failNode); err != nil {
		return err
	}
	return stageCheckpoint(cfg)
}

func stageParse(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	wf, err := parser.ParseFile(cfg.workflow, pol.Epoch)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	if err := sm.Save("normalized.json", wf); err != nil {
		return err
	}
	dig, err := parser.CanonicalDigest(wf)
	if err != nil {
		return err
	}
	return sm.Save("workflow_digest.json", map[string]string{"digest": dig, "workflow_id": wf.ID})
}

func stageCompile(cfg paths) error {
	sm := state.New(cfg.state)
	var wf model.Workflow
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	plan, err := compiler.Compile(&wf)
	if err != nil {
		return err
	}
	if err := sm.Save("compiled.json", plan); err != nil {
		return err
	}
	if err := dag.Validate(&wf, plan); err != nil {
		_ = sm.Save("compile_diagnostics.json", map[string]string{"error": err.Error()})
		return fmt.Errorf("compile validation: %w", err)
	}
	return nil
}

func stageSchedule(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var plan model.ExecutionPlan
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("compiled.json", &plan); err != nil {
		return err
	}
	assignments, err := scheduler.Schedule(&plan, &wf, pol)
	if err != nil {
		return err
	}
	return sm.Save("schedule.json", map[string]any{
		"workflow_id": wf.ID,
		"assignments": assignments,
		"workers":     pol.Workers,
	})
}

func stageExecute(cfg paths, failNode string) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var plan model.ExecutionPlan
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("compiled.json", &plan); err != nil {
		return err
	}
	var sched struct {
		Assignments []scheduler.Assignment `json:"assignments"`
	}
	if err := sm.Load("schedule.json", &sched); err != nil {
		return err
	}
	store := cache.New(cfg.cache)
	rec, jlog, err := executor.Run(&wf, &plan, sched.Assignments, pol, store, failNode)
	if err != nil {
		return err
	}
	if err := sm.Save("execution.json", rec); err != nil {
		return err
	}
	if err := jlog.Save(journal.Path(cfg.state)); err != nil {
		return err
	}
	return util.WriteJSON(filepath.Join(cfg.output, "execution.json"), rec)
}

func stageCheckpoint(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var rec model.ExecutionRecord
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("execution.json", &rec); err != nil {
		return err
	}
	jlog, err := journal.Load(journal.Path(cfg.state))
	if err != nil {
		return err
	}
	cpStore := checkpoint.NewStore(cfg.checkpoints)

	half := rec
	if len(half.Results) > 2 {
		half.Results = half.Results[:len(half.Results)/2]
		half.Status = "partial"
	}
	cp1, err := checkpoint.Create(&wf, &half, jlog, 1, "", pol.Epoch)
	if err != nil {
		return err
	}
	if err := cpStore.Save(cp1); err != nil {
		return err
	}
	cp2, err := checkpoint.Create(&wf, &rec, jlog, 2, cp1.ID, pol.Epoch)
	if err != nil {
		return err
	}
	merged, err := checkpoint.MergeIncremental(cp1, cp2)
	if err != nil {
		return err
	}
	if err := cpStore.Save(cp2); err != nil {
		return err
	}
	// Persist merged as version 2 tip identity for recovery selection tests.
	merged.Version = 2
	if err := cpStore.Save(merged); err != nil {
		return err
	}
	rec.CheckpointID = merged.ID
	_ = sm.Save("execution.json", rec)
	return sm.Save("checkpoints.json", map[string]any{
		"latest": merged,
		"v1":     cp1,
		"v2":     cp2,
	})
}

func stageRecover(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var plan model.ExecutionPlan
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("compiled.json", &plan); err != nil {
		return err
	}
	cpStore := checkpoint.NewStore(cfg.checkpoints)
	result, recovered, err := recovery.Recover(&wf, &plan, cpStore, pol)
	if err != nil {
		return err
	}
	if err := sm.Save("recovery.json", result); err != nil {
		return err
	}
	if err := sm.Save("recovered_checkpoint.json", recovered); err != nil {
		return err
	}
	return util.WriteJSON(filepath.Join(cfg.output, "recovery.json"), result)
}

func stageReplay(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var rec model.ExecutionRecord
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("execution.json", &rec); err != nil {
		return err
	}
	jlog, err := journal.Load(journal.Path(cfg.state))
	if err != nil {
		return err
	}
	rr, err := replay.Build(&wf, &rec, jlog, pol)
	if err != nil {
		return err
	}
	if err := sm.Save("replay.json", rr); err != nil {
		return err
	}
	return util.WriteJSON(filepath.Join(cfg.output, "replay.json"), rr)
}

func stageVerify(cfg paths) error {
	sm := state.New(cfg.state)
	var wf model.Workflow
	var plan model.ExecutionPlan
	var rec model.ExecutionRecord
	var rr model.ReplayRecord
	var recovered model.Checkpoint
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("compiled.json", &plan); err != nil {
		return err
	}
	if err := sm.Load("execution.json", &rec); err != nil {
		return err
	}
	if err := sm.Load("replay.json", &rr); err != nil {
		return err
	}
	if err := sm.Load("recovered_checkpoint.json", &recovered); err != nil {
		return err
	}
	report, err := verification.Verify(&wf, &plan, &rec, &recovered, &rr)
	if err != nil {
		return err
	}
	if err := sm.Save("verification.json", report); err != nil {
		return err
	}
	return util.WriteJSON(filepath.Join(cfg.output, "verification.json"), report)
}

func stageCertificate(cfg paths) error {
	pol, err := policy.Load(cfg.policy)
	if err != nil {
		return err
	}
	token, err := certificate.LoadToken(cfg.token)
	if err != nil {
		return err
	}
	sm := state.New(cfg.state)
	var wf model.Workflow
	var plan model.ExecutionPlan
	var rec model.ExecutionRecord
	var rr model.ReplayRecord
	var recoveryResult model.RecoveryResult
	var report model.VerificationReport
	if err := sm.Load("normalized.json", &wf); err != nil {
		return err
	}
	if err := sm.Load("compiled.json", &plan); err != nil {
		return err
	}
	if err := sm.Load("execution.json", &rec); err != nil {
		return err
	}
	if err := sm.Load("replay.json", &rr); err != nil {
		return err
	}
	if err := sm.Load("recovery.json", &recoveryResult); err != nil {
		return err
	}
	if err := sm.Load("verification.json", &report); err != nil {
		return err
	}
	cert, err := certificate.Issue(&wf, &plan, &rec, &rr, &recoveryResult, &report, token, pol.Epoch)
	if err != nil {
		return err
	}
	if err := sm.Save("certificate.json", cert); err != nil {
		return err
	}
	if err := util.WriteJSON(filepath.Join(cfg.output, "certificate.json"), cert); err != nil {
		return err
	}
	ok := certificate.Verify(cert, token)
	return util.WriteJSON(filepath.Join(cfg.output, "certificate_status.json"), map[string]any{
		"valid": ok, "workflow_id": wf.ID, "body_digest": cert.BodyDigest,
	})
}

func env(k, def string) string {
	if v := os.Getenv(k); v != "" {
		return v
	}
	return def
}

func must(err error) {
	if err != nil {
		fmt.Fprintf(os.Stderr, "fatal: %v\n", err)
		os.Exit(1)
	}
}

func dumpJSON(v any) string {
	b, _ := json.MarshalIndent(v, "", "  ")
	return string(b)
}
