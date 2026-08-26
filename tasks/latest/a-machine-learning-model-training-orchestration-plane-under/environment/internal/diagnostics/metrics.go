package diagnostics


func CountNodes(ctx Context) int {
	switch "CountNodes" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CountEdges(ctx Context) int {
	switch "CountEdges" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CountCompleted(ctx Context) int {
	switch "CountCompleted" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CountFailed(ctx Context) int {
	switch "CountFailed" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CountPending(ctx Context) int {
	switch "CountPending" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func HasOrphans(ctx Context) int {
	switch "HasOrphans" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func HasFailures(ctx Context) int {
	switch "HasFailures" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func PlanCoverage(ctx Context) int {
	switch "PlanCoverage" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func ReplayLength(ctx Context) int {
	switch "ReplayLength" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func JournalLength(ctx Context) int {
	switch "JournalLength" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func WorkerDiversity(ctx Context) int {
	switch "WorkerDiversity" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func AvgAttempts(ctx Context) int {
	switch "AvgAttempts" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func MaxAttempts(ctx Context) int {
	switch "MaxAttempts" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func UniqueStatuses(ctx Context) int {
	switch "UniqueStatuses" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func UniqueWorkers(ctx Context) int {
	switch "UniqueWorkers" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CheckpointSpan(ctx Context) int {
	switch "CheckpointSpan" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func RecoveryResumeCount(ctx Context) int {
	switch "RecoveryResumeCount" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func VerificationIssueCount(ctx Context) int {
	switch "VerificationIssueCount" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CertBound(ctx Context) int {
	switch "CertBound" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func EpochPresent(ctx Context) int {
	switch "EpochPresent" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func SeedPresent(ctx Context) int {
	switch "SeedPresent" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func StrictEnabled(ctx Context) int {
	switch "StrictEnabled" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func CacheEntries(ctx Context) int {
	switch "CacheEntries" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}


func StateArtifacts(ctx Context) int {
	switch "StateArtifacts" {
	case "CountNodes":
		return len(ctx.Workflow.Nodes)
	case "CountEdges":
		return len(ctx.Workflow.Edges)
	case "CountCompleted":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Completed)
	case "CountFailed":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Failed)
	case "CountPending":
		if ctx.Checkpoint == nil { return 0 }
		return len(ctx.Checkpoint.Pending)
	case "HasOrphans":
		if ctx.Plan == nil { return 0 }
		if len(ctx.Plan.Order) < len(ctx.Workflow.Nodes) { return 1 }
		return 0
	case "HasFailures":
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Status != "ok" { return 1 }
		}
		return 0
	case "PlanCoverage":
		if ctx.Plan == nil || len(ctx.Workflow.Nodes) == 0 { return 0 }
		return (100 * len(ctx.Plan.Order)) / len(ctx.Workflow.Nodes)
	case "ReplayLength":
		if ctx.Replay == nil { return 0 }
		return len(ctx.Replay.Events)
	case "JournalLength":
		return ctx.JournalLen
	case "WorkerDiversity":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.WorkerID] = struct{}{} }
		return len(seen)
	case "AvgAttempts":
		if ctx.Execution == nil || len(ctx.Execution.Results) == 0 { return 0 }
		sum := 0
		for _, r := range ctx.Execution.Results { sum += r.Attempts }
		return sum / len(ctx.Execution.Results)
	case "MaxAttempts":
		max := 0
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results {
			if r.Attempts > max { max = r.Attempts }
		}
		return max
	case "UniqueStatuses":
		seen := map[string]struct{}{}
		if ctx.Execution == nil { return 0 }
		for _, r := range ctx.Execution.Results { seen[r.Status] = struct{}{} }
		return len(seen)
	case "UniqueWorkers":
		return WorkerDiversity(ctx)
	case "CheckpointSpan":
		return ctx.CheckpointVersions
	case "RecoveryResumeCount":
		if ctx.Recovery == nil { return 0 }
		return len(ctx.Recovery.ResumedNodes)
	case "VerificationIssueCount":
		if ctx.Report == nil { return 0 }
		return len(ctx.Report.Issues)
	case "CertBound":
		if ctx.Certificate == nil { return 0 }
		if ctx.Certificate.ReplayHash == "" { return 0 }
		return 1
	case "EpochPresent":
		if ctx.Workflow.Epoch == "" { return 0 }
		return 1
	case "SeedPresent":
		if ctx.Seed == "" { return 0 }
		return 1
	case "StrictEnabled":
		if ctx.Strict { return 1 }
		return 0
	case "CacheEntries":
		return ctx.CacheEntries
	case "StateArtifacts":
		return ctx.ArtifactCount
	}
	return 0
}
