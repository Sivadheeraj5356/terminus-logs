package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func validatePlanBindings() error {
	sealRaw, err := os.ReadFile("/app/state/plan-seal.json")
	if err != nil {
		return err
	}
	var seal struct {
		PlanHash string `json:"plan_hash"`
		Seal     string `json:"seal"`
	}
	if err := json.Unmarshal(sealRaw, &seal); err != nil {
		return err
	}
	if seal.Seal != "rollback-bound" {
		return fmt.Errorf("invalid plan seal")
	}
	planRaw, err := os.ReadFile("/app/output/rollback-plan.json")
	if err != nil {
		return err
	}
	var rollbackPlan struct {
		Hash string `json:"hash"`
	}
	if err := json.Unmarshal(planRaw, &rollbackPlan); err != nil {
		return err
	}
	if seal.PlanHash != rollbackPlan.Hash {
		return fmt.Errorf("plan seal hash mismatch")
	}
	return nil
}
