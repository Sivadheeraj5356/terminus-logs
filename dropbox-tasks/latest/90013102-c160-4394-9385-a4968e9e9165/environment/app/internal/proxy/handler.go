package proxy

import (
	"crypto/rand"
	"encoding/hex"
	"net"

	"sigproxy/internal/audit"
	"sigproxy/internal/config"
	"sigproxy/internal/keyring"
	"sigproxy/internal/semantics"
	"sigproxy/internal/signature"
	"sigproxy/internal/spool"
	"sigproxy/internal/trace"
	"sigproxy/internal/wire"
)

type Handler struct {
	Runtime  *config.Runtime
	TraceW   *trace.Writer
	AuditW   *audit.SnapshotWriter
	SpoolW   *spool.Writer
	Mode     string
}

func (h *Handler) HandleConn(conn net.Conn) {
	defer conn.Close()
	raw, err := wire.ReadFullRequest(conn)
	if err != nil || len(raw) == 0 {
		return
	}
	resp := h.processRequest(raw)
	_, _ = conn.Write(resp)
}

func hasCompleteRequest(buf []byte) bool {
	if len(buf) < 4 {
		return false
	}
	// crude: headers ended
	for i := 0; i+3 < len(buf); i++ {
		if buf[i] == '\r' && buf[i+1] == '\n' && buf[i+2] == '\r' && buf[i+3] == '\n' {
			return true
		}
	}
	return false
}

func (h *Handler) processRequest(raw []byte) []byte {
	wreq, err := wire.Parse(raw)
	if err != nil {
		return RejectResponse("parse_error")
	}

	if err := semantics.ValidateBody(wreq.EntityBody, h.Runtime.Config.BodyLimit); err != nil {
		return ErrorResponse(413, "body_limit_exceeded")
	}

	profileHeader := wire.HeaderFirst(wreq.Headers, "X-Sig-Profile")
	pc, err := h.Runtime.Catalog.SelectByHeader(profileHeader)
	if err != nil {
		return RejectResponse("unknown_profile")
	}
	prof, policy, _ := semantics.ProfileFromConfig(pc)

	method, err := semantics.NormalizeMethod(wreq.Method)
	if err != nil {
		return RejectResponse("invalid_method")
	}

	path, query, target, pairs, err := semantics.NormalizeTarget(prof, wreq.Target)
	if err != nil {
		return RejectResponse("invalid_target")
	}

	tenant := wire.HeaderFirst(wreq.Headers, "X-Sig-Tenant")
	keyID := wire.HeaderFirst(wreq.Headers, "X-Sig-Key-Id")
	nonce := wire.HeaderFirst(wreq.Headers, "X-Sig-Nonce")
	sigHeader := wire.HeaderFirst(wreq.Headers, "X-Signature")
	authority := wire.HeaderFirst(wreq.Headers, "Host")

	requestID := wire.HeaderFirst(wreq.Headers, "X-Request-Id")
	if requestID == "" {
		requestID = newRequestID()
	}

	verifyHeaders, err := semantics.ApplyPreVerifyHeaders(policy, wreq.Headers, wreq.HeaderOrder)
	if err != nil {
		return RejectResponse("header_policy_violation")
	}
	verifyHeaders = semantics.FilterSignedHeaders(policy, verifyHeaders)

	verifySem := &semantics.Request{
		RequestID:           requestID,
		SignatureVersion:    pc.SignatureVersion,
		ProfileID:           pc.ID,
		ProfileEpoch:        pc.Epoch,
		Tenant:              tenant,
		KeyID:               keyID,
		KeyEpoch:            keyEpochFromKeyring(h.Runtime.Keyring, tenant, keyID),
		Method:              method,
		Authority:           authority,
		CanonicalPath:       path,
		CanonicalQuery:      query,
		CanonicalQueryPairs: pairs,
		CanonicalTarget:     target,
		CanonicalHeaders:    verifyHeaders,
		EntityBody:          append([]byte(nil), wreq.EntityBody...),
		EntityBodySHA256:    semantics.BodyDigest(wreq.EntityBody),
		EntityBodyLength:    len(wreq.EntityBody),
		RequestNonce:        nonce,
	}

	ver := signature.Verify(verifySem, sigHeader, h.Runtime.Keyring, h.Runtime.Cache, h.Runtime.Catalog.CatalogDigest)
	if !ver.OK {
		return RejectResponse(ver.Reason)
	}

	// Forward path uses post-filter headers
	forwardHeaders, err := semantics.ApplyHeaderPolicy(policy, wreq.Headers, wreq.HeaderOrder)
	if err != nil {
		return RejectResponse("header_policy_violation")
	}
	forwardHeaders = semantics.FilterSignedHeaders(policy, forwardHeaders)

	forwardSem := verifySem.Clone()
	forwardSem.CanonicalHeaders = forwardHeaders

	decision := DecideRetry(h.Runtime.Config.BackendUnix, true)
	var resp []byte
	var fwd *trace.ForwardEvidence
	var sp *trace.SpoolEvidence

	if decision.Queue {
		rec := spool.NewRecord(requestID, 0, wreq.WireDigest(), forwardSem.Clone(), sigHeader, ver.CanonicalDigest)
		if err := h.SpoolW.Write(rec, raw, wreq.EntityBody); err != nil {
			return ErrorResponse(500, "spool_write_failed")
		}
		sp = &trace.SpoolEvidence{RecordID: rec.RecordID, State: string(spool.StatePending), ReplayCount: 0, SealValid: true}
		resp = RetryResponse()
	} else {
		out, err := ForwardSemantic(h.Runtime.Config.BackendUnix, forwardSem)
		if err != nil {
			rec := spool.NewRecord(requestID, 0, wreq.WireDigest(), forwardSem.Clone(), sigHeader, ver.CanonicalDigest)
			_ = h.SpoolW.Write(rec, raw, wreq.EntityBody)
			sp = &trace.SpoolEvidence{RecordID: rec.RecordID, State: string(spool.StatePending), ReplayCount: 0, SealValid: true}
			resp = RetryResponse()
		} else {
			// mutate forwardSem after forward for audit bug demonstration
			forwardSem.CanonicalTarget = stringsToUpperPath(forwardSem.CanonicalTarget)
			fwd = &trace.ForwardEvidence{
				BackendDigest:  out.BackendDigest,
				BackendLength:  out.BackendLength,
				Forwarded:      true,
				ResponseStatus: out.StatusCode,
			}
			resp = out.ResponseBody
			if len(resp) == 0 {
				resp = []byte("HTTP/1.1 200 OK\r\nContent-Length: 2\r\n\r\nOK")
			}
		}
	}

	snap := audit.CaptureAfterForward(forwardSem, "live", "allow", audit.ReasonAllow, ver.CanonicalDigest, ver.CacheHit)
	auditDigest, _ := h.AuditW.WriteSnapshot(snap)
	h.TraceW.AddFromSnapshot(snap, wreq.WireDigest(), len(wreq.EntityBody), fwd, sp, auditDigest)
	_ = h.TraceW.Flush()

	return resp
}

func keyEpochFromKeyring(kr *keyring.Keyring, tenant, keyID string) int {
	for _, k := range kr.Keys {
		if k.Tenant == tenant && k.KeyID == keyID {
			return k.KeyEpoch
		}
	}
	return 1
}

func newRequestID() string {
	b := make([]byte, 8)
	_, _ = rand.Read(b)
	return hex.EncodeToString(b)
}

func stringsToUpperPath(p string) string {
	// cosmetic mutation for audit mismatch on some requests
	if p == "" {
		return p
	}
	return p
}
