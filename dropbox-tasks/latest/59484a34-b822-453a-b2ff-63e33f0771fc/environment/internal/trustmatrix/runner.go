package trustmatrix

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"

	"github.com/privco/ctpki/internal/ctproof"
	"github.com/privco/ctpki/internal/bundlewalk"
	"github.com/privco/ctpki/internal/pkitypes"
	"github.com/privco/ctpki/internal/proofgate"
	"github.com/privco/ctpki/internal/revoke"
	"github.com/privco/ctpki/internal/roottrust"
	"github.com/privco/ctpki/internal/serialdup"
	"github.com/privco/ctpki/internal/sthclock"
)

func trustScore(disposition, reason string) int {
	switch disposition {
	case "trusted":
		return 100
	case "needs_review":
		return 50
	}
	switch reason {
	case "revoked":
		return 0
	case "wrong_tree_size":
		return 12
	case "duplicate_serial":
		return 8
	case "stale_sth":
		return 18
	case "untrusted_root":
		return 22
	case "invalid_chain":
		return 15
	default:
		return 0
	}
}

func Run(bundleRoot, snapshotPath, reportPath string) error {
	metaBytes, err := os.ReadFile(filepath.Join(bundleRoot, "bundle_meta.json"))
	if err != nil {
		return err
	}
	var meta struct {
		BundleID string `json:"bundle_id"`
	}
	if err := json.Unmarshal(metaBytes, &meta); err != nil {
		return err
	}
	snap, err := bundlewalk.ReadSnapshot(snapshotPath)
	if err != nil {
		return err
	}
	certs, err := loadCerts(bundleRoot)
	if err != nil {
		return err
	}
	entries, err := loadEntries(bundleRoot)
	if err != nil {
		return err
	}
	entryByKey := map[string]pkitypes.CTEntry{}
	for _, e := range entries {
		entryByKey[fmt.Sprintf("%s:%d", e.Serial, e.LeafIndex)] = e
	}
	sth, err := loadSTH(bundleRoot)
	if err != nil {
		return err
	}
	proofs, err := loadProofs(bundleRoot)
	if err != nil {
		return err
	}
	dupSerials, err := duplicateSerials(bundleRoot)
	if err != nil {
		return err
	}
	anchors := "/app/trusted_roots.json"
	if p := filepath.Join(bundleRoot, "trusted_roots.json"); fileExists(p) {
		anchors = p
	}
	revPath := filepath.Join(bundleRoot, "revocations.json")

	var rows []pkitypes.DispositionRow
	for _, row := range snap.Rows {
		cert := certsByFilename(certs, row.Filename)
		entry := entryByKey[fmt.Sprintf("%s:%d", row.Serial, row.LeafIndex)]
		if entry.LeafHash == "" {
			entry.LeafHash = row.LeafHash
		}
		disp := "rejected"
		reason := "unknown"

		if revoke.Revoked(revPath, row.Serial) {
			reason = "revoked"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if dupSerials[row.Serial] {
			reason = "duplicate_serial"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if !roottrust.ChainValid(cert.IssuerSerial, cert.SignatureOK) {
			reason = "invalid_chain"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if !roottrust.RootTrusted(anchors, cert.IssuerSerial) {
			reason = "untrusted_root"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if !proofgate.HasProof(proofs, proofKey(row.Serial, row.LeafIndex)) {
			disp = proofgate.MissingProofDisposition()
			reason = "missing_proof"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		proof := proofs[proofKey(row.Serial, row.LeafIndex)]
		if !sthclock.Consistent(sth.Timestamp, entry.Timestamp) {
			reason = "stale_sth"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if proof.TreeSize != sth.TreeSize {
			reason = "wrong_tree_size"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		if !ctproof.ProofValid(entry, proof, sth) {
			reason = "wrong_tree_size"
			rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
			continue
		}
		disp = "trusted"
		reason = "ok"
		rows = append(rows, pkitypes.DispositionRow{Serial: row.Serial, Disposition: disp, Reason: reason, TrustScore: trustScore(disp, reason)})
	}
	report := pkitypes.DispositionReport{BundleID: meta.BundleID, Rows: rows}
	if err := os.MkdirAll(filepath.Dir(reportPath), 0o755); err != nil {
		return err
	}
	b, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(reportPath, append(b, '\n'), 0o644)
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func loadCerts(bundleRoot string) (map[string]pkitypes.Certificate, error) {
	dir := filepath.Join(bundleRoot, "certificates")
	ents, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	out := map[string]pkitypes.Certificate{}
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		b, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, err
		}
		var cert pkitypes.Certificate
		if err := json.Unmarshal(b, &cert); err != nil {
			return nil, err
		}
		if cert.Filename == "" {
			cert.Filename = e.Name()
		}
		out[cert.Filename] = cert
	}
	return out, nil
}

func certsByFilename(certs map[string]pkitypes.Certificate, filename string) pkitypes.Certificate {
	if c, ok := certs[filename]; ok {
		return c
	}
	return pkitypes.Certificate{}
}

func loadEntries(bundleRoot string) ([]pkitypes.CTEntry, error) {
	b, err := os.ReadFile(filepath.Join(bundleRoot, "ct_logs", "b161aa7f_entries.jsonl"))
	if err != nil {
		return nil, err
	}
	var out []pkitypes.CTEntry
	for _, line := range splitLines(string(b)) {
		if line == "" {
			continue
		}
		var e pkitypes.CTEntry
		if err := json.Unmarshal([]byte(line), &e); err != nil {
			return nil, err
		}
		out = append(out, e)
	}
	return out, nil
}

func loadSTH(bundleRoot string) (pkitypes.STH, error) {
	b, err := os.ReadFile(filepath.Join(bundleRoot, "ct_logs", "sth.json"))
	if err != nil {
		return pkitypes.STH{}, err
	}
	var sth pkitypes.STH
	return sth, json.Unmarshal(b, &sth)
}

func proofKey(serial string, leafIndex int) string {
	return fmt.Sprintf("%s:%d", serial, leafIndex)
}

func loadProofs(bundleRoot string) (map[string]pkitypes.InclusionProof, error) {
	dir := filepath.Join(bundleRoot, "ct_logs", "proofs")
	ents, err := os.ReadDir(dir)
	if err != nil {
		return map[string]pkitypes.InclusionProof{}, nil
	}
	out := map[string]pkitypes.InclusionProof{}
	for _, e := range ents {
		if e.IsDir() {
			continue
		}
		b, err := os.ReadFile(filepath.Join(dir, e.Name()))
		if err != nil {
			return nil, err
		}
		var proof pkitypes.InclusionProof
		if err := json.Unmarshal(b, &proof); err != nil {
			return nil, err
		}
		out[proofKey(proof.Serial, proof.LeafIndex)] = proof
	}
	return out, nil
}

func duplicateSerials(bundleRoot string) (map[string]bool, error) {
	issuance, err := serialdup.LoadIssuance(filepath.Join(bundleRoot, "issuance.json"))
	if err != nil {
		return map[string]bool{}, nil
	}
	bySerial := map[string][]serialdup.IssuanceRow{}
	for _, row := range issuance {
		bySerial[row.Serial] = append(bySerial[row.Serial], row)
	}
	dup := map[string]bool{}
	for serial, rows := range bySerial {
		if len(rows) >= 2 {
			dup[serial] = true
		}
	}
	return dup, nil
}

func duplicateLosers(bundleRoot string) (map[string]bool, error) {
	issuance, err := serialdup.LoadIssuance(filepath.Join(bundleRoot, "issuance.json"))
	if err != nil {
		return map[string]bool{}, nil
	}
	bySerial := map[string][]serialdup.IssuanceRow{}
	for _, row := range issuance {
		bySerial[row.Serial] = append(bySerial[row.Serial], row)
	}
	losers := map[string]bool{}
	for _, rows := range bySerial {
		if len(rows) < 2 {
			continue
		}
		winner := rows[0]
		for _, cand := range rows[1:] {
			if serialdup.KeepNewest(cand, winner) {
				winner = cand
			}
		}
		for _, row := range rows {
			if row.Filename != winner.Filename {
				losers[row.Filename] = true
			}
		}
	}
	return losers, nil
}

func splitLines(s string) []string {
	var out []string
	start := 0
	for i := 0; i < len(s); i++ {
		if s[i] == '\n' {
			out = append(out, s[start:i])
			start = i + 1
		}
	}
	if start < len(s) {
		out = append(out, s[start:])
	}
	return out
}
