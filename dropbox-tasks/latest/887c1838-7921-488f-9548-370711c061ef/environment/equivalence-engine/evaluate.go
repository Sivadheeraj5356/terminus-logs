package engine

import "artifactequiv/artifact-registry"

// SessionFile is the on-disk build session payload (see /app/references/session_format.md).
type SessionFile struct {
	SessionID    string `json:"session_id"`
	CrossCompile bool   `json:"cross_compile"`
	Toolchains   []struct {
		ID     string `json:"id"`
		Triple string `json:"triple"`
	} `json:"toolchains"`
	Checkpoints []struct {
		Seq            int    `json:"seq"`
		Stage          string `json:"stage"`
		Toolchain      string `json:"toolchain"`
		ArtifactHash   string `json:"artifact_hash"`
		SymbolDigest   string `json:"symbol_digest"`
		CompressedSize int    `json:"compressed_size"`
		RawSize        int    `json:"raw_size"`
	} `json:"checkpoints"`
	Events []struct {
		Seq          int    `json:"seq"`
		Toolchain    string `json:"toolchain"`
		Stage        string `json:"stage"`
		Op           string `json:"op"`
		ArtifactRef  string `json:"artifact_ref"`
		PrevHash     string `json:"prev_hash"`
		NewHash      string `json:"new_hash"`
		SymbolDigest string `json:"symbol_digest"`
	} `json:"events"`
	Rollbacks []struct {
		Attempt              int    `json:"attempt"`
		FailedStage          string `json:"failed_stage"`
		RestoredCheckpoint   int    `json:"restored_checkpoint"`
		ExpectedSymbolDigest string `json:"expected_symbol_digest"`
		ActualSymbolDigest   string `json:"actual_symbol_digest"`
	} `json:"rollbacks"`
	Shards []struct {
		ShardID          string `json:"shard_id"`
		Worker           string `json:"worker"`
		EventSeqs        []int  `json:"event_seqs"`
		ContributionHash string `json:"contribution_hash"`
	} `json:"shards"`
	OptimizationPasses []struct {
		PassID              string `json:"pass_id"`
		Toolchain           string `json:"toolchain"`
		BehaviorFingerprint string `json:"behavior_fingerprint"`
	} `json:"optimization_passes"`
	Stress *struct {
		Schedules []struct {
			ScheduleID    string `json:"schedule_id"`
			EventSeqOrder []int  `json:"event_seq_order"`
		} `json:"schedules"`
	} `json:"stress,omitempty"`
}

// EvaluateSession replays compilation events and validates cross-toolchain equivalence.
func EvaluateSession(sf SessionFile) registry.SessionResult {
	panic("engine.EvaluateSession not implemented")
}
