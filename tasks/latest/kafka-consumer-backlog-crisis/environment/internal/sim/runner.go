package sim

import (
	"streamkit/internal/config"
	"streamkit/internal/consumer"
	"streamkit/internal/model"
)

type RunStats struct {
	RecordsProcessed int
	Ticks            int
	CommitCount      int
	FinalResidual    int
	PeakResidual     int
}

func RunScenario(sc model.Scenario, profile config.RuntimeProfile, tickBudget int) (RunStats, *consumer.Session) {
	sess := consumer.NewSession(sc, profile)
	stats := RunStats{}

	for tick := 0; tick < tickBudget; tick++ {
		progress := false
		for m := 0; m < len(sess.Members.Members); m++ {
			units := sess.PollMember(m, tick)
			for _, unit := range units {
				if len(unit.Records) == 0 {
					continue
				}
				progress = true
				last := unit.Records[len(unit.Records)-1].Offset + 1
				sess.Offsets.Set(unit.Partition, last)
				n := len(unit.Records)
				stats.RecordsProcessed += n
				sess.Journal.Add(n)
				lastPull := 1
				if profile.MarkScaleByPull {
					lastPull = n
				}
				if sess.Journal.TryFlush(sc.CommitIntervalRecords, lastPull) {
					stats.CommitCount++
				}
			}
		}
		residual := totalResidual(sess)
		if residual > stats.PeakResidual {
			stats.PeakResidual = residual
		}
		if stats.RecordsProcessed >= sess.Topic.TotalRecords() {
			stats.Ticks = tick + 1
			stats.FinalResidual = residual
			return stats, sess
		}
		if !progress && residual == 0 {
			stats.Ticks = tick + 1
			stats.FinalResidual = 0
			return stats, sess
		}
	}
	stats.Ticks = tickBudget
	stats.FinalResidual = totalResidual(sess)
	return stats, sess
}

func totalResidual(sess *consumer.Session) int {
	total := 0
	for p := 0; p < sess.Scenario.Partitions; p++ {
		total += sess.Topic.Lag(p, sess.Offsets.Get(p))
	}
	return total
}
