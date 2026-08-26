package sim

import (
	"math"

	"streamkit/internal/consumer"
	"streamkit/internal/model"
)

const SimulatedSecondsPerTick = 0.01

func placementSignature(loads []int) int {
	sig := 0
	for i, load := range loads {
		sig += (i + 1) * load
	}
	return sig
}

func idleMembers(loads []int) int {
	idle := 0
	for _, load := range loads {
		if load == 0 {
			idle++
		}
	}
	return idle
}

func BuildResult(sc model.Scenario, stats RunStats, sess *consumer.Session) model.ScenarioResult {
	throughput := 0.0
	if stats.Ticks > 0 {
		seconds := float64(stats.Ticks) * SimulatedSecondsPerTick
		throughput = float64(stats.RecordsProcessed) / seconds
	}
	commitsPer1000 := 0.0
	if stats.RecordsProcessed > 0 {
		commitsPer1000 = (float64(stats.CommitCount) / float64(stats.RecordsProcessed)) * 1000.0
	}
	loads := consumer.MemberLoads(sess)
	return model.ScenarioResult{
		ScenarioID:              sc.ID,
		RecordsProcessed:        stats.RecordsProcessed,
		TicksElapsed:            stats.Ticks,
		FinalResidualRecords:    stats.FinalResidual,
		PeakTickResidual:        stats.PeakResidual,
		ThroughputRecordsPerSec: math.Round(throughput*100) / 100,
		CommitsPer1000Records:   math.Round(commitsPer1000*100) / 100,
		AssignmentSpread:        consumer.MemberSpread(sess),
		MemberLoads:             loads,
		IdleMemberCount:         idleMembers(loads),
		PlacementSignature:      placementSignature(loads),
	}
}
