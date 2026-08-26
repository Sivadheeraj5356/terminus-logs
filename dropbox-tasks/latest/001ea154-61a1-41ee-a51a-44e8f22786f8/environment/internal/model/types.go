package model

type Record struct {
	Offset int    `json:"offset"`
	Key    string `json:"key"`
	Value  string `json:"value"`
}

type Member struct {
	ID        string `json:"id"`
	Partition []int  `json:"partition_ids"`
}

type Scenario struct {
	ID                    string `json:"scenario_id"`
	Partitions            int    `json:"partitions"`
	Members               int    `json:"members"`
	RecordsPerPartition   int    `json:"records_per_partition"`
	MaxPollRecords        int    `json:"max_poll_records"`
	MinFetchBytes         int    `json:"min_fetch_bytes"`
	CommitIntervalRecords int    `json:"commit_interval_records"`
}

type WorkloadFile struct {
	Scenarios  []Scenario `json:"scenarios"`
	TickBudget int        `json:"tick_budget"`
}

type ScenarioResult struct {
	ScenarioID              string  `json:"scenario_id"`
	RecordsProcessed        int     `json:"records_processed"`
	TicksElapsed            int     `json:"ticks_elapsed"`
	FinalResidualRecords    int     `json:"final_residual_records"`
	PeakTickResidual        int     `json:"peak_tick_residual"`
	ThroughputRecordsPerSec float64 `json:"throughput_records_per_sec"`
	CommitsPer1000Records   float64 `json:"commits_per_1000_records"`
	AssignmentSpread        int     `json:"assignment_spread"`
	MemberLoads             []int   `json:"member_loads"`
	IdleMemberCount         int     `json:"idle_member_count"`
	PlacementSignature      int     `json:"placement_signature"`
}

type RecoveryReport struct {
	Scenarios      []ScenarioResult `json:"scenarios"`
	RecoveryDigest string           `json:"recovery_digest"`
}
