package main

import "rollbackctl/internal/rbx_d4"

func runPlan(args []string) error {
	out := "/app/output/rollback-plan.json"
	for i := 0; i < len(args); i++ {
		if args[i] == "--out" && i+1 < len(args) {
			out = args[i+1]
		}
	}
	return rbxd4.Emit(out)
}
