# Selene lunar survival board-game planner

Write the player bot for Selene, a deterministic turn-based lunar colony survival board game. Each sol is one game turn: choose the crew's ration policy and colony action, resolve the published hazard for that turn, satisfy the end-of-campaign charter, and emit the winning game replay with its resource ledger.

The required Go entry point is `/workspace/task_file/main.go`. It is run from `/workspace` with:

```sh
go run /workspace/task_file/main.go
```

The player bot reads the game scenario from `/workspace/task_file/colony.json` and replaces `/workspace/colony_plan.json`. It must not modify the scenario, use the network, randomness, the clock, environment-specific values, or helper processes. Replaying the same scenario must replace any previous output with the same bytes. Compatible game boards are substituted during grading, so behavior must derive from the scenario rather than its public `case_id` or event sequence.

`/workspace/task_file/CHARTER_SPEC.md` is the authoritative game-rule and data-format contract. It defines valid scenario fields, turn resolution order, move eligibility, resource accounting, campaign feasibility, the complete-campaign objective, replay schema, canonical ordering, empty and impossible campaigns, malformed input, and numeric types. The supplied `/workspace/task_file/colony.json` is only the public game board.

The replay is graded exactly after JSON parsing. Arrays are order-sensitive, JSON integers are numbers, strings and lowercase enum values match exactly, and extra or missing fields fail grading. The final tie-break compares the complete campaign key rather than an individual move. `/workspace/colony_plan.json` must contain only the required JSON artifact, with no logs or explanatory text.
