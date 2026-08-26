package main

import (
	"flag"
	"fmt"
	"os"
	"path/filepath"

	"odip/internal/cleargate"
	"odip/internal/decyclose"
	"odip/internal/epochseal"
	"odip/internal/gatechain"
	"odip/internal/planwrite"
	"odip/internal/poolclash"
	"odip/internal/rolljournal"
	"odip/internal/scenpack"
	"odip/internal/slotbind"
	"odip/internal/supersede"
	"odip/internal/unitfan"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "usage: odip <stage|plan|run> ...")
		os.Exit(2)
	}
	switch os.Args[1] {
	case "stage":
		os.Exit(cmdStage(os.Args[2:]))
	case "plan":
		os.Exit(cmdPlan(os.Args[2:]))
	case "run":
		os.Exit(cmdRun(os.Args[2:]))
	default:
		fmt.Fprintf(os.Stderr, "unknown command %q\n", os.Args[1])
		os.Exit(2)
	}
}

func defaultPolicy() string { return "/app/fixtures/policies/approval_policy.json" }

func toEdges(deps []scenpack.DepEdge) []decyclose.Edge {
	out := make([]decyclose.Edge, len(deps))
	for i, e := range deps {
		out[i] = decyclose.Edge{From: e.From, To: e.To}
	}
	return out
}

func cmdStage(args []string) int {
	fs := flag.NewFlagSet("stage", flag.ContinueOnError)
	scenario := fs.String("scenario", "", "scenario directory")
	policy := fs.String("policy", defaultPolicy(), "approval policy")
	out := fs.String("out", "/app/state/odip/impact_lattice.json", "lattice output")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *scenario == "" {
		fmt.Fprintln(os.Stderr, "--scenario required")
		return 2
	}
	sc, err := scenpack.LoadScenario(*scenario)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if _, err := scenpack.LoadPolicy(*policy); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	lat, err := buildLattice(sc)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := planwrite.WriteLattice(*out, lat); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdPlan(args []string) int {
	fs := flag.NewFlagSet("plan", flag.ContinueOnError)
	lattice := fs.String("lattice", "", "lattice path")
	policy := fs.String("policy", defaultPolicy(), "approval policy")
	out := fs.String("out", "/app/output/decision_impact_plan.json", "plan output")
	journal := fs.String("journal", rolljournal.DefaultPath, "rollout journal path")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *lattice == "" {
		fmt.Fprintln(os.Stderr, "--lattice required")
		return 2
	}
	lat, err := planwrite.ReadLattice(*lattice)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	pol, err := scenpack.LoadPolicy(*policy)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	prior, found, err := rolljournal.LatestForScenario(*journal, lat.ScenarioID)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if found && !supersede.Allow(prior.RolloutEpoch, lat.RolloutEpoch) {
		fmt.Fprintf(os.Stderr, "superseded rollout epoch %d (prior %d)\n", lat.RolloutEpoch, prior.RolloutEpoch)
		return 4
	}
	plan, err := buildPlan(lat, pol)
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := os.MkdirAll(filepath.Dir(*out), 0o755); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := planwrite.WritePlan(*out, plan); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	if err := rolljournal.Append(*journal, rolljournal.Entry{
		ScenarioID:       plan.ScenarioID,
		RolloutEpoch:     plan.RolloutEpoch,
		PlanDigest:       plan.PlanDigest,
		LatticeDigest:    lat.LatticeDigest,
		EpochSeal:        plan.EpochSeal,
		TopologyRevision: plan.TopologyRevision,
		WindowDigest:     plan.WindowDigest,
		BookingDigest:    plan.BookingDigest,
	}); err != nil {
		fmt.Fprintln(os.Stderr, err)
		return 1
	}
	return 0
}

func cmdRun(args []string) int {
	fs := flag.NewFlagSet("run", flag.ContinueOnError)
	scenario := fs.String("scenario", "", "scenario directory")
	policy := fs.String("policy", defaultPolicy(), "approval policy")
	stage := fs.String("stage", "/app/state/odip/impact_lattice.json", "lattice path")
	out := fs.String("out", "/app/output/decision_impact_plan.json", "plan output")
	journal := fs.String("journal", rolljournal.DefaultPath, "rollout journal path")
	if err := fs.Parse(args); err != nil {
		return 2
	}
	if *scenario == "" {
		fmt.Fprintln(os.Stderr, "--scenario required")
		return 2
	}
	if code := cmdStage([]string{"--scenario", *scenario, "--policy", *policy, "--out", *stage}); code != 0 {
		return code
	}
	return cmdPlan([]string{"--lattice", *stage, "--policy", *policy, "--out", *out, "--journal", *journal})
}

func buildLattice(sc *scenpack.Scenario) (*planwrite.Lattice, error) {
	cycle, path := decyclose.DetectCycle(sc.DecisionIDs, toEdges(sc.DepEdges))
	impacts := unitfan.FanOut(sc.Decisions, sc.TopoEdges)
	lat := &planwrite.Lattice{
		SchemaVersion:    "odip.lattice.v1",
		ScenarioID:       sc.Meta.ScenarioID,
		RolloutEpoch:     sc.Meta.RolloutEpoch,
		TopologyRevision: sc.Meta.TopologyRevision,
		DecisionIDs:      append([]string(nil), sc.DecisionIDs...),
		UnitIDs:          append([]string(nil), sc.UnitIDs...),
		DependencyEdges:  sc.DepEdges,
		ImpactRows:       impacts,
		ResourceBookings: sc.Bookings,
		CycleDetected:    cycle,
		CyclePath:        path,
		Decisions:        sc.Decisions,
		Meta:             sc.Meta,
		Windows:          sc.Windows,
		Exclusive:        sc.Exclusive,
		Flags:            sc.Flags,
		Clearances:       sc.Clearances,
		Classes:          sc.Classes,
	}
	lat.LatticeDigest = planwrite.LatticeDigest(lat)
	return lat, nil
}

func buildPlan(lat *planwrite.Lattice, pol *scenpack.Policy) (*planwrite.Plan, error) {
	order := []string{}
	if !lat.CycleDetected {
		order = decyclose.TopoOrder(lat.DecisionIDs, toEdges(lat.DependencyEdges))
	}
	approvals := gatechain.BuildSteps(order, lat, pol)
	conflicts := poolclash.FindConflicts(lat)
	regs := cleargate.RegulatoryBlocks(lat)
	feasible := !lat.CycleDetected && len(conflicts) == 0 && len(regs) == 0
	if lat.CycleDetected {
		order = []string{}
	}
	plan := &planwrite.Plan{
		SchemaVersion:      "odip.plan.v1",
		ScenarioID:         lat.ScenarioID,
		RolloutEpoch:       lat.RolloutEpoch,
		TopologyRevision:   lat.TopologyRevision,
		BoundLatticeDigest: lat.LatticeDigest,
		EpochSeal: epochseal.ComputeSeal(
			lat.LatticeDigest,
			lat.RolloutEpoch,
			lat.ScenarioID,
			lat.TopologyRevision,
		),
		WindowDigest:     slotbind.WindowDigest(lat.Windows, lat.Exclusive),
		BookingDigest:    slotbind.BookingDigest(lat.ResourceBookings),
		ExecutionOrder:   order,
		ApprovalSteps:    approvals,
		Conflicts:        conflicts,
		RegulatoryBlocks: regs,
		Feasible:         feasible,
		CycleDetected:    lat.CycleDetected,
		CyclePath:        lat.CyclePath,
	}
	plan.PlanDigest = planwrite.PlanDigest(plan)
	return plan, nil
}
