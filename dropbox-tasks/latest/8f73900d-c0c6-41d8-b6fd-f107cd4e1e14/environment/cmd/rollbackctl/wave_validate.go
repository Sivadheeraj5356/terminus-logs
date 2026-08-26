package main

import (
	"encoding/json"
	"fmt"
	"os"

	"rollbackctl/internal/rbx_c3"
	rbxd4 "rollbackctl/internal/rbx_d4"
	"rollbackctl/internal/rbx_h8"
	"rollbackctl/internal/rbx_i9"
)

func runValidate(args []string) error {
	graphPath := "/app/data/topology/rollback-graph.json"
	for i := 0; i < len(args); i++ {
		if args[i] == "--graph" && i+1 < len(args) {
			graphPath = args[i+1]
		}
	}
	if err := rbxc3.ValidateNoCycle(graphPath); err != nil {
		return err
	}
	if graphPath != "/app/data/topology/rollback-graph.json" {
		return nil
	}
	if err := rbxd4.VerifyManifestDigestBindings(); err != nil {
		return err
	}
	if err := validatePlanBindings(); err != nil {
		return err
	}
	planRaw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	var rollbackPlan struct {
		Steps []string `json:"steps"`
	}
	if err := json.Unmarshal(planRaw, &rollbackPlan); err != nil {
		return err
	}
	g, err := rbxc3.Load("/app/data/topology/rollback-graph.json")
	if err != nil {
		return err
	}
	if !rbxc3.ValidRollbackOrder(rollbackPlan.Steps, g) {
		return fmt.Errorf("invalid rollback order")
	}
	if err := rbxi9.VerifyTopologyEpochLatch(); err != nil {
		return err
	}
	return rbxh8.WriteWitnessBundle()
}
