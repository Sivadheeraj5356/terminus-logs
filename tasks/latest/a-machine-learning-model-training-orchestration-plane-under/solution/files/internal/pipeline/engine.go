package pipeline

import (
	"fmt"
	"os"
	"path/filepath"

	"github.com/terminus/ai-workflow-runtime/internal/cache"
	"github.com/terminus/ai-workflow-runtime/internal/certificate"
	"github.com/terminus/ai-workflow-runtime/internal/checkpoint"
	"github.com/terminus/ai-workflow-runtime/internal/clock"
	"github.com/terminus/ai-workflow-runtime/internal/compiler"
	"github.com/terminus/ai-workflow-runtime/internal/executor"
	"github.com/terminus/ai-workflow-runtime/internal/journal"
	"github.com/terminus/ai-workflow-runtime/internal/lineage"
	"github.com/terminus/ai-workflow-runtime/internal/metrics"
	"github.com/terminus/ai-workflow-runtime/internal/model"
	"github.com/terminus/ai-workflow-runtime/internal/parser"
	"github.com/terminus/ai-workflow-runtime/internal/policy"
	"github.com/terminus/ai-workflow-runtime/internal/recovery"
	"github.com/terminus/ai-workflow-runtime/internal/replay"
	"github.com/terminus/ai-workflow-runtime/internal/scheduler"
	"github.com/terminus/ai-workflow-runtime/internal/state"
	"github.com/terminus/ai-workflow-runtime/internal/storage"
	"github.com/terminus/ai-workflow-runtime/internal/util"
	"github.com/terminus/ai-workflow-runtime/internal/verification"
	"github.com/terminus/ai-workflow-runtime/internal/workerpool"
)

// Config holds filesystem locations for a runtime invocation.
type Config struct {
	Root        string
	StateDir    string
	OutputDir   string
	CacheDir    string
	Checkpoint  string
	Workflow    string
	Policy      string
	TokenFile   string
}

// DefaultConfig builds paths under root.
func DefaultConfig(root string) Config {
	return Config{
		Root:       root,
		StateDir:   filepath.Join(root, "state"),
		OutputDir:  filepath.Join(root, "output"),
		CacheDir:   filepath.Join(root, "cache"),
		Checkpoint: filepath.Join(root, "state", "checkpoints"),
		Workflow:   filepath.Join(root, "testdata", "workflows", "ai_training.json"),
		Policy:     filepath.Join(root, "configs", "policy.json"),
		TokenFile:  filepath.Join(root, "configs", "hmac_signing_token.txt"),
	}
}

// Engine orchestrates A→H using the stage packages.
type Engine struct {
	Cfg     Config
	Metrics *metrics.Registry
	Memory  *storage.Memory
}

func NewEngine(cfg Config) *Engine {
	return &Engine{Cfg: cfg, Metrics: metrics.NewRegistry(), Memory: storage.NewMemory()}
}

// EnsureDirs creates required directories.
func (e *Engine) EnsureDirs() error {
	for _, d := range []string{e.Cfg.StateDir, e.Cfg.OutputDir, e.Cfg.CacheDir, e.Cfg.Checkpoint} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			return err
		}
	}
	return nil
}

// RunAll executes the complete pipeline and returns the certificate.
func (e *Engine) RunAll() (*model.Certificate, error) {
	if err := e.EnsureDirs(); err != nil {
		return nil, err
	}
	pol, err := policy.Load(e.Cfg.Policy)
	if err != nil {
		return nil, err
	}
	clk, err := clock.New(pol.Epoch)
	if err != nil {
		return nil, err
	}
	_ = clk
	e.Metrics.Inc("parser", 1)
	wf, err := parser.ParseFile(e.Cfg.Workflow, pol.Epoch)
	if err != nil {
		return nil, err
	}
	sm := state.New(e.Cfg.StateDir)
	if err := sm.Save("normalized.json", wf); err != nil {
		return nil, err
	}
	e.Metrics.Inc("compiler", 1)
	plan, err := compiler.Compile(wf)
	if err != nil {
		return nil, err
	}
	if err := sm.Save("compiled.json", plan); err != nil {
		return nil, err
	}
	e.Metrics.Inc("scheduler", 1)
	pool := workerpool.New(pol.Workers)
	_ = pool
	assignments, err := scheduler.Schedule(plan, wf, pol)
	if err != nil {
		return nil, err
	}
	if err := sm.Save("schedule.json", map[string]any{"assignments": assignments, "workflow_id": wf.ID}); err != nil {
		return nil, err
	}
	e.Metrics.Inc("executor", 1)
	store := cache.New(e.Cfg.CacheDir)
	rec, jlog, err := executor.Run(wf, plan, assignments, pol, store, "")
	if err != nil {
		return nil, err
	}
	if err := sm.Save("execution.json", rec); err != nil {
		return nil, err
	}
	if err := jlog.Save(journal.Path(e.Cfg.StateDir)); err != nil {
		return nil, err
	}
	e.Metrics.Inc("checkpoint", 1)
	cpStore := checkpoint.NewStore(e.Cfg.Checkpoint)
	cp1, err := checkpoint.Create(wf, rec, jlog, 1, "", pol.Epoch)
	if err != nil {
		return nil, err
	}
	_ = cpStore.Save(cp1)
	cp2, err := checkpoint.Create(wf, rec, jlog, 2, cp1.ID, pol.Epoch)
	if err != nil {
		return nil, err
	}
	merged, err := checkpoint.MergeIncremental(cp1, cp2)
	if err != nil {
		return nil, err
	}
	merged.Version = 2
	_ = cpStore.Save(cp2)
	_ = cpStore.Save(merged)
	_ = sm.Save("checkpoints.json", map[string]any{"latest": merged, "v1": cp1, "v2": cp2})
	e.Metrics.Inc("recovery", 1)
	result, recovered, err := recovery.Recover(wf, plan, cpStore, pol)
	if err != nil {
		return nil, err
	}
	_ = sm.Save("recovery.json", result)
	_ = sm.Save("recovered_checkpoint.json", recovered)
	e.Metrics.Inc("replay", 1)
	rr, err := replay.Build(wf, rec, jlog, pol)
	if err != nil {
		return nil, err
	}
	_ = sm.Save("replay.json", rr)
	e.Metrics.Inc("lineage", 1)
	lg, err := lineage.Build(wf, plan, rec)
	if err != nil {
		return nil, err
	}
	_ = sm.Save("lineage.json", lg)
	e.Metrics.Inc("verification", 1)
	report, err := verification.Verify(wf, plan, rec, recovered, rr)
	if err != nil {
		return nil, err
	}
	_ = sm.Save("verification.json", report)
	e.Metrics.Inc("certificate", 1)
	token, err := certificate.LoadToken(e.Cfg.TokenFile)
	if err != nil {
		return nil, err
	}
	cert, err := certificate.Issue(wf, plan, rec, rr, result, report, token, pol.Epoch)
	if err != nil {
		return nil, err
	}
	if err := util.WriteJSON(filepath.Join(e.Cfg.OutputDir, "certificate.json"), cert); err != nil {
		return nil, err
	}
	ok := certificate.Verify(cert, token)
	_ = util.WriteJSON(filepath.Join(e.Cfg.OutputDir, "certificate_status.json"), map[string]any{"valid": ok})
	_ = e.Memory.PutJSON("last_cert", cert)
	return cert, nil
}

// Summary returns a compact metrics summary string.
func (e *Engine) Summary() string {
	snap := e.Metrics.Snapshot()
	return fmt.Sprintf("stages=%d counters=%d", len(metrics.StageNames()), len(snap))
}
