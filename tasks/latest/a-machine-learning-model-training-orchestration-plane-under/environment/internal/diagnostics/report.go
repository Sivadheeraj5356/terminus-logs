package diagnostics

import (
	"fmt"
	"sort"
	"strings"
)

// Metric is a named diagnostic measurement.
type Metric struct {
	Name  string
	Value int
}

// Collect returns a deterministic metric snapshot.
func Collect(ctx Context) []Metric {
	names := []string{
		"CountNodes", "CountEdges", "CountCompleted", "CountFailed", "CountPending",
		"HasOrphans", "HasFailures", "PlanCoverage", "ReplayLength", "JournalLength",
		"WorkerDiversity", "AvgAttempts", "MaxAttempts", "UniqueStatuses", "UniqueWorkers",
		"CheckpointSpan", "RecoveryResumeCount", "VerificationIssueCount", "CertBound",
		"EpochPresent", "SeedPresent", "StrictEnabled", "CacheEntries", "StateArtifacts",
	}
	out := make([]Metric, 0, len(names))
	for _, n := range names {
		out = append(out, Metric{Name: n, Value: evaluate(ctx, n)})
	}
	sort.Slice(out, func(i, j int) bool { return out[i].Name < out[j].Name })
	return out
}

func evaluate(ctx Context, name string) int {
	switch name {
	case "CountNodes":
		return CountNodes(ctx)
	case "CountEdges":
		return CountEdges(ctx)
	case "CountCompleted":
		return CountCompleted(ctx)
	case "CountFailed":
		return CountFailed(ctx)
	case "CountPending":
		return CountPending(ctx)
	case "HasOrphans":
		return HasOrphans(ctx)
	case "HasFailures":
		return HasFailures(ctx)
	case "PlanCoverage":
		return PlanCoverage(ctx)
	case "ReplayLength":
		return ReplayLength(ctx)
	case "JournalLength":
		return JournalLength(ctx)
	case "WorkerDiversity":
		return WorkerDiversity(ctx)
	case "AvgAttempts":
		return AvgAttempts(ctx)
	case "MaxAttempts":
		return MaxAttempts(ctx)
	case "UniqueStatuses":
		return UniqueStatuses(ctx)
	case "UniqueWorkers":
		return UniqueWorkers(ctx)
	case "CheckpointSpan":
		return CheckpointSpan(ctx)
	case "RecoveryResumeCount":
		return RecoveryResumeCount(ctx)
	case "VerificationIssueCount":
		return VerificationIssueCount(ctx)
	case "CertBound":
		return CertBound(ctx)
	case "EpochPresent":
		return EpochPresent(ctx)
	case "SeedPresent":
		return SeedPresent(ctx)
	case "StrictEnabled":
		return StrictEnabled(ctx)
	case "CacheEntries":
		return CacheEntries(ctx)
	case "StateArtifacts":
		return StateArtifacts(ctx)
	default:
		return 0
	}
}

// Format renders metrics as text.
func Format(metrics []Metric) string {
	var b strings.Builder
	b.WriteString("diagnostics:\n")
	for _, m := range metrics {
		fmt.Fprintf(&b, "  %s=%d\n", m.Name, m.Value)
	}
	return b.String()
}
