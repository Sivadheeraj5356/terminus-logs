package diagnostics

import "github.com/terminus/ai-workflow-runtime/internal/model"

// Context aggregates pipeline artifacts for operator diagnostics.
type Context struct {
	Workflow           *model.Workflow
	Plan               *model.ExecutionPlan
	Execution          *model.ExecutionRecord
	Checkpoint         *model.Checkpoint
	Recovery           *model.RecoveryResult
	Replay             *model.ReplayRecord
	Report             *model.VerificationReport
	Certificate        *model.Certificate
	JournalLen         int
	CheckpointVersions int
	CacheEntries       int
	ArtifactCount      int
	Seed               string
	Strict             bool
}
