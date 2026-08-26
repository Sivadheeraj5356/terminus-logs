package seal

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
)

func hashBlob(parts ...[]byte) string {
	h := sha256.New()
	for i, p := range parts {
		if i > 0 {
			_, _ = h.Write([]byte{'\n'})
		}
		_, _ = h.Write(p)
	}
	sum := h.Sum(nil)
	return hex.EncodeToString(sum)
}

func readSortedDir(dir string) ([]byte, error) {
	entries, err := os.ReadDir(dir)
	if err != nil {
		return nil, err
	}
	names := []string{}
	for _, ent := range entries {
		if ent.IsDir() {
			continue
		}
		names = append(names, ent.Name())
	}
	sort.Strings(names)
	var blob []byte
	for _, name := range names {
		raw, err := os.ReadFile(filepath.Join(dir, name))
		if err != nil {
			return nil, err
		}
		blob = append(blob, raw...)
		blob = append(blob, '\n')
	}
	return blob, nil
}

func tableHashOf(data string) (string, error) {
	paths := []string{
		filepath.Join(data, "num_auth", "gain_map.json"),
		filepath.Join(data, "num_auth", "ref_weights.json"),
		filepath.Join(data, "num_auth", "fringe_map.json"),
		filepath.Join(data, "num_auth", "coupling.json"),
		filepath.Join(data, "num_auth", "generation.json"),
		filepath.Join(data, "tb_state", "clock.json"),
	}
	var parts [][]byte
	for _, p := range paths {
		raw, err := os.ReadFile(p)
		if err != nil {
			return "", err
		}
		parts = append(parts, raw)
	}
	live, err := readSortedDir(filepath.Join(data, "bands_live"))
	if err != nil {
		return "", err
	}
	shadow, err := readSortedDir(filepath.Join(data, "bands_shadow"))
	if err != nil {
		return "", err
	}
	parts = append(parts, live, shadow)
	return hashBlob(parts...), nil
}

func appendLedger(path string, record map[string]any) error {
	body, err := json.Marshal(record)
	if err != nil {
		return err
	}
	f, err := os.OpenFile(path, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.Write(append(body, '\n'))
	return err
}

type sealComputed struct {
	report        map[string]any
	full          ScoreArm
	auth          LocaleBundle
	tableHash     string
	expectedBind  string
	authorityOK   bool
	metaOK        bool
}

func computeSeal(data string, tip HeadState, requireAgree bool) (sealComputed, error) {
	var out sealComputed
	auth, err := fuseLocales(data)
	if err != nil {
		return out, err
	}
	th, err := tableHashOf(data)
	if err != nil {
		return out, err
	}
	clockRaw, err := os.ReadFile(filepath.Join(data, "tb_state", "clock.json"))
	if err != nil {
		return out, err
	}
	expectedBind := epochBindHex(clockRaw, th)

	weights := map[string]float64{}
	for k, v := range auth.Locales {
		weights[k] = v.Weight
	}
	stiff, err := loadFloatMap(filepath.Join(data, "num_auth", "gain_map.json"))
	if err != nil {
		return out, err
	}
	damp, err := loadFloatMap(filepath.Join(data, "num_auth", "fringe_map.json"))
	if err != nil {
		return out, err
	}
	cpl, err := loadFloatMap(filepath.Join(data, "num_auth", "coupling.json"))
	if err != nil {
		return out, err
	}
	bounds, err := loadBounds(filepath.Join(data, "num_auth", "family_intervals.json"))
	if err != nil {
		return out, err
	}
	cells, err := loadCells(filepath.Join(data, "fixtures"))
	if err != nil {
		return out, err
	}

	full := scoreArm(cells, stiff, damp, cpl, weights, bounds)
	perm := scoreArm(permuteCells(cells), rotateModeMap(stiff), rotateModeMap(damp), rotateModeMap(cpl), weights, bounds)
	rev := scoreArm(reverseCells(cells), stiff, damp, cpl, reverseWeights(weights), bounds)
	composeCells := reverseCells(permuteCells(cells))
	compose := scoreArm(composeCells, rotateModeMap(stiff), rotateModeMap(damp), rotateModeMap(cpl), reverseWeights(weights), bounds)
	chain := chainDigest(full.Digest, perm.Digest, rev.Digest, compose.Digest)

	authorityOK := auth.Agreement || !requireAgree
	metaOK := full.Digest == perm.Digest && full.Digest == rev.Digest && full.Digest == compose.Digest
	mismatched := auth.Mismatched
	if mismatched == nil {
		mismatched = []string{}
	}

	panelsOut := map[string]any{}
	for pid, ps := range full.Panels {
		panelsOut[pid] = ps
	}

	lineage := tip.LineageID
	if lineage == 0 {
		lineage = 1
	}

	report := map[string]any{
		"annex_slice":                  19,
		"authority_agreement":          authorityOK,
		"authority_mismatched_locales": mismatched,
		"digest_full":                  full.Digest,
		"digest_permute_modes":         perm.Digest,
		"digest_reverse_locale_bands":  rev.Digest,
		"digest_cascade_compose":       compose.Digest,
		"chain_digest":                 chain,
		"metamorphic_equivalent":       metaOK,
		"panels":                       panelsOut,
		"total_bound_violations":       full.TotalViolations,
		"max_observed_tightness":       full.MaxTightness,
		"table_hash":                   th,
		"epoch_bind":                   expectedBind,
		"peel_source":                  auth.PeelSource,
		"epoch":                        auth.Epoch,
		"lineage_id":                   lineage,
		"journal_generation":           tip.Generation + 1,
		"engine":                       "mode_seal",
		"resumed":                      false,
	}
	out.report = report
	out.full = full
	out.auth = auth
	out.tableHash = th
	out.expectedBind = expectedBind
	out.authorityOK = authorityOK
	out.metaOK = metaOK
	return out, nil
}

func writeReport(outDir string, report map[string]any) error {
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	body, err := json.MarshalIndent(report, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(outDir, "invariant_proof_log.json"), append(body, '\n'), 0o644)
}

func RunClose(root string) error {
	data := filepath.Join(root, "data")
	outDir := filepath.Join(root, "output")
	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}

	ctrlRaw, err := os.ReadFile(filepath.Join(data, "qv7_ctl", "controls.json"))
	if err != nil {
		return err
	}
	var controls map[string]any
	if err := json.Unmarshal(ctrlRaw, &controls); err != nil {
		return err
	}
	requireAgree := mustBool(controls, "require_authority_agreement", true)
	resume := mustBool(controls, "resume_from_checkpoint", false)

	journal := filepath.Join(data, "ms_store", "mesh.wal")
	tipPath := filepath.Join(data, "ms_store", "tip.json")
	bindPath := filepath.Join(data, "ms_store", "seal.bind")
	tip, err := recoverHead(journal, tipPath, bindPath)
	if err != nil {
		return err
	}

	th, err := tableHashOf(data)
	if err != nil {
		return err
	}
	clockRaw, err := os.ReadFile(filepath.Join(data, "tb_state", "clock.json"))
	if err != nil {
		return err
	}
	expectedBind := epochBindHex(clockRaw, th)

	headStale := false
	if raw, err := os.ReadFile(tipPath); err == nil {
		headStale = tipMarkedStale(string(raw))
	}
	bindOK := false
	if eb, thb, lid, ok := loadEpochBind(bindPath); ok {
		bindOK = eb == tip.EpochBind && thb == tip.TableHash && lid == tip.LineageID && eb == expectedBind
	}
	digestOK := len(tip.DigestFull) == 64 && len(tip.ChainDigest) == 64
	hashOK := len(tip.TableHash) == 64 && tip.TableHash == th
	cleanHead := tip.TotalBoundViolations == 0 && tip.Generation > 0 && tip.EpochBind == expectedBind
	if resume && !headStale && digestOK && hashOK && cleanHead && bindOK {
		computed, err := computeSeal(data, tip, requireAgree)
		if err != nil {
			return err
		}
		// Rebuild the full public report; keep durable tip/bind/journal unchanged.
		if computed.report["digest_full"] == tip.DigestFull &&
			computed.report["chain_digest"] == tip.ChainDigest &&
			computed.tableHash == tip.TableHash &&
			computed.expectedBind == tip.EpochBind &&
			computed.full.TotalViolations == 0 {
			computed.report["resumed"] = true
			computed.report["lineage_id"] = tip.LineageID
			computed.report["journal_generation"] = tip.Generation
			if err := writeReport(outDir, computed.report); err != nil {
				return err
			}
			fmt.Fprintln(os.Stderr, "seal resumed from tip without rematerialize")
			return nil
		}
		// Tip looked clean but live recompute disagreed — fall through and rematerialize.
	}

	computed, err := computeSeal(data, tip, requireAgree)
	if err != nil {
		return err
	}
	if err := writeReport(outDir, computed.report); err != nil {
		return err
	}

	full := computed.full
	auth := computed.auth
	th = computed.tableHash
	expectedBind = computed.expectedBind
	lineage := tip.LineageID
	if lineage == 0 {
		lineage = 1
	}
	chainDigest, _ := computed.report["chain_digest"].(string)

	payloadObj := map[string]any{
		"digest_full":            full.Digest,
		"table_hash":             th,
		"chain_digest":           chainDigest,
		"epoch_bind":             expectedBind,
		"lineage_id":             lineage,
		"total_bound_violations": full.TotalViolations,
	}
	payload, _ := json.Marshal(payloadObj)
	frame := Frame{Generation: tip.Generation + 1, Payload: string(payload)}
	if err := appendFrame(journal, frame); err != nil {
		return err
	}
	frames, err := loadFrames(journal)
	if err != nil {
		return err
	}
	fresh := HeadState{
		Generation:           frame.Generation,
		DigestFull:           full.Digest,
		TableHash:            th,
		ChainDigest:          chainDigest,
		EpochBind:            expectedBind,
		LineageID:            lineage,
		TotalBoundViolations: full.TotalViolations,
		FramesKept:           len(frames),
	}
	if err := writeHeadJSON(tipPath, fresh); err != nil {
		return err
	}
	if err := writeEpochBind(bindPath, fresh); err != nil {
		return err
	}
	_ = appendLedger(filepath.Join(data, "tb_state", "ledger.jsonl"), map[string]any{
		"epoch":        auth.Epoch,
		"peel_source":  auth.PeelSource,
		"table_hash":   th,
		"epoch_bind":   expectedBind,
		"chain_digest": computed.report["chain_digest"],
		"generation":   fresh.Generation,
		"lineage_id":   lineage,
	})

	if !computed.authorityOK || !computed.metaOK || full.TotalViolations != 0 {
		fmt.Fprintf(os.Stderr, "seal incomplete: violations=%d authority_ok=%v meta_ok=%v peel=%s epoch=%d\n",
			full.TotalViolations, computed.authorityOK, computed.metaOK, auth.PeelSource, auth.Epoch)
	} else {
		fmt.Println("seal closed: zero violations, metamorphic digests agree")
	}
	return nil
}
