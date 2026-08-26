package spool

import (
	"encoding/hex"
	"os"

	"sigproxy/internal/audit"
	"sigproxy/internal/backend"
	"sigproxy/internal/config"
	"sigproxy/internal/semantics"
	"sigproxy/internal/signature"
	"sigproxy/internal/trace"
	"sigproxy/internal/wire"
)

type ReplayResult struct {
	RecordID  string
	Forwarded bool
	Reason    audit.ReasonCode
}

// ReplayPending replays all pending spool records.
func ReplayPending(rt *config.Runtime, backendUnix string, traceW *trace.Writer, auditW *audit.SnapshotWriter, sealKeyHex string) ([]ReplayResult, error) {
	key, err := hex.DecodeString(sealKeyHex)
	if err != nil {
		key = []byte("demo-spool-seal-key-32-bytes!!")
	}
	pending, err := ListPending(rt.Config.SpoolDir)
	if err != nil {
		return nil, err
	}
	writer, _ := NewWriter(rt.Config.SpoolDir, sealKeyHex)
	var results []ReplayResult
	for _, rec := range pending {
		res := replayOne(rt, backendUnix, traceW, auditW, writer, rec, key)
		results = append(results, res)
	}
	return results, nil
}

func replayOne(rt *config.Runtime, backendUnix string, traceW *trace.Writer, auditW *audit.SnapshotWriter, writer *Writer, rec *Record, sealKey []byte) ReplayResult {
	if !VerifySeal(rec, sealKey) {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonIntegrityFailure}
	}

	key, ok := rt.Keyring.Lookup(rec.SemanticRequest.Tenant, rec.SemanticRequest.KeyID, rec.SemanticRequest.KeyEpoch)
	if !ok || key.Revoked {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonReplayQuarantine}
	}

	raw, err := os.ReadFile(rec.RawWirePath)
	if err != nil {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonIntegrityFailure}
	}

	wreq, err := wire.Parse(raw)
	if err != nil {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonIntegrityFailure}
	}

	pc, ok := rt.Catalog.Lookup(rec.SemanticRequest.ProfileID, rec.SemanticRequest.ProfileEpoch)
	if !ok {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonReplayQuarantine}
	}
	prof, policy, _ := semantics.ProfileFromConfig(pc)

	sem, err := rebuildFromWire(wreq, prof, policy, rec.SemanticRequest)
	if err != nil {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonHeaderPolicy}
	}

	ver := signature.Verify(sem, rec.SignatureHeader, rt.Keyring, rt.Cache, rt.Catalog.CatalogDigest)
	if !ver.OK {
		rec.State = StateQuarantine
		_ = writer.Update(rec)
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonSignatureMismatch}
	}

	rec.ReplayCount++
	fwd, err := backend.ForwardSemantic(backendUnix, sem)
	if err != nil {
		return ReplayResult{RecordID: rec.RecordID, Forwarded: false, Reason: audit.ReasonReplayQuarantine}
	}

	rec.State = StateCompleted
	_ = writer.Update(rec)

	snap := audit.CaptureAfterForward(sem, "spool", "allow", audit.ReasonAllow, ver.CanonicalDigest, ver.CacheHit)
	auditDigest, _ := auditW.WriteSnapshot(snap)
	traceW.AddFromSnapshot(snap, rec.WireDigest, len(sem.EntityBody), &trace.ForwardEvidence{
		BackendDigest:  fwd.BackendDigest,
		BackendLength:  fwd.BackendLength,
		Forwarded:      true,
		ResponseStatus: fwd.StatusCode,
	}, &trace.SpoolEvidence{
		RecordID:    rec.RecordID,
		State:       string(rec.State),
		ReplayCount: rec.ReplayCount,
		SealValid:   true,
	}, auditDigest)

	return ReplayResult{RecordID: rec.RecordID, Forwarded: true, Reason: audit.ReasonAllow}
}

func rebuildFromWire(wreq *wire.Request, prof *semantics.Profile, policy semantics.HeaderPolicy, stored *semantics.Request) (*semantics.Request, error) {
	method, err := semantics.NormalizeMethod(wreq.Method)
	if err != nil {
		return nil, err
	}
	path, query, target, pairs, err := semantics.NormalizeTarget(prof, wreq.Target)
	if err != nil {
		return nil, err
	}
	headers, err := semantics.ApplyPreVerifyHeaders(policy, wreq.Headers, wreq.HeaderOrder)
	if err != nil {
		return nil, err
	}
	headers = semantics.FilterSignedHeaders(policy, headers)

	body := wreq.EntityBody

	sem := &semantics.Request{
		RequestID:           stored.RequestID,
		SignatureVersion:    stored.SignatureVersion,
		ProfileID:           stored.ProfileID,
		ProfileEpoch:        stored.ProfileEpoch,
		Tenant:              stored.Tenant,
		KeyID:               stored.KeyID,
		KeyEpoch:            stored.KeyEpoch,
		Method:              method,
		Authority:           wire.HeaderFirst(wreq.Headers, "Host"),
		CanonicalPath:       path,
		CanonicalQuery:      query,
		CanonicalQueryPairs: pairs,
		CanonicalTarget:     target,
		CanonicalHeaders:    headers,
		EntityBody:          append([]byte(nil), body...),
		EntityBodySHA256:    semantics.BodyDigest(body),
		EntityBodyLength:    len(body),
		RequestNonce:        stored.RequestNonce,
	}
	return sem, nil
}
