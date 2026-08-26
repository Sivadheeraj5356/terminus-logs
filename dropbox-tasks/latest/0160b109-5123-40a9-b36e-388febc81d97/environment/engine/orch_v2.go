package engine

import (
	"encoding/binary"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"ucg.local/workspace/r2v"
	"ucg.local/workspace/s9k"
	"ucg.local/workspace/t4w"
)

type RunOpts struct {
	Arm   string
	Phase string
	Root  string
	Out   string
}

func RunPipeline(opts RunOpts) error {
	coeffPath := filepath.Join(opts.Root, "data", "coeff_seed.tsv")
	armPath := filepath.Join(opts.Root, "data", "arm_ladder.toml")
	edgePath := filepath.Join(opts.Root, "data", "edge_seed.toml")
	coeffs, err := LoadCoeffs(coeffPath)
	if err != nil {
		return err
	}
	order, err := LoadArmOrder(armPath, opts.Arm)
	if err != nil {
		return err
	}
	salt, err := LoadArmSalt(armPath, opts.Arm)
	if err != nil {
		return err
	}
	edges, err := LoadConversionEdges(edgePath)
	if err != nil {
		return err
	}

	tip, hasTip := ReadJournalTip(opts.Out)
	if opts.Phase == "replay" || (opts.Phase == "warm" && WarmNeedsMutation(tip, opts.Arm, opts.Phase)) {
		touch, delta, merr := LoadMutation(armPath)
		if merr == nil {
			if row, ok := coeffs[touch]; ok {
				row.Step += delta
				coeffs[touch] = row
			}
		}
	}
	_ = hasTip

	var expanded []string
	for _, id := range order {
		expanded = append(expanded, id, id+"_echo")
	}

	durable := map[string]*r2v.PackState{}
	cacheDir := filepath.Join(opts.Out, "cache")
	cacheLoaded := 0
	cacheDropped := 0
	accept := ShouldAcceptCache(cacheDir, opts.Arm)
	if opts.Phase == "warm" || opts.Phase == "replay" {
		entries, _ := os.ReadDir(cacheDir)
		for _, ent := range entries {
			name := ent.Name()
			if !strings.HasSuffix(name, ".bin") {
				continue
			}
			id := strings.TrimSuffix(name, ".bin")
			raw, err := os.ReadFile(filepath.Join(cacheDir, name))
			if err != nil || len(raw) < 8 {
				cacheDropped++
				continue
			}
			if !accept {
				cacheDropped++
				continue
			}
			p := r2v.NewPack()
			p.Blob = append([]byte(nil), raw[:8]...)
			durable[id] = p
			cacheLoaded++
		}
	}

	facets := map[string]uint64{}
	gateFirst := false
	ordCode := uint32(0)

	useCache := PreferCachedFacets(opts.Phase, accept, durable, expanded, tip, opts.Arm, DigestHex)
	if useCache {
		for _, id := range expanded {
			if p := durable[id]; p != nil && len(p.Blob) >= 8 {
				facets[id] = binary.BigEndian.Uint64(p.Blob[:8])
			}
		}
	} else {
		for _, id := range expanded {
			cr, ok := coeffs[id]
			if !ok {
				continue
			}
			var got uint64
			side := func() {
				got = FoldCoeff(cr.Step, cr.Family, cr.Prev, salt)
			}
			gate := func() {
				facets[id] = got
			}
			ordCode = s9k.Order(gateFirst, side, gate)
		}
		_ = ordCode

		ApplyConversionEdges(facets, edges)
		SyncEchoFacets(facets)

		for i, id := range expanded {
			cr, ok := coeffs[id]
			if !ok {
				continue
			}
			facet := facets[id]
			stamp := cr.Step
			if strings.HasSuffix(id, "_echo") {
				base := strings.TrimSuffix(id, "_echo")
				if br, ok := coeffs[base]; ok {
					stamp = br.Step
				}
			}
			src := r2v.NewPack()
			var buf [8]byte
			binary.BigEndian.PutUint64(buf[:], facet)
			src.Blob = buf[:]
			src.Stamp = uint32(i + 1)
			dst := durable[id]
			if dst == nil {
				dst = r2v.NewPack()
			}
			_ = BindPack(dst, src, uint32(stamp))
			durable[id] = dst
			if len(dst.Blob) >= 8 {
				facet = binary.BigEndian.Uint64(dst.Blob[:8])
			}
			facets[id] = facet
		}
	}

	rowRecs := []t4w.RowRec{}
	bundle := &t4w.BundleRec{Coeffs: map[string]uint64{}}
	wit := &t4w.WitRec{Expected: map[string]uint64{}, PackHex: map[string]string{}}

	for _, id := range expanded {
		facet := facets[id]
		bundle.Coeffs[id] = facet
		wit.Expected[id] = facet
		wit.PackHex[id] = fmt.Sprintf("%016x", facet)
		rowRecs = append(rowRecs, t4w.RowRec{ID: id, Facet: facet})
	}

	emitted := EmitRows(rowRecs, bundle, wit)

	_ = os.MkdirAll(cacheDir, 0o755)
	for id, p := range durable {
		if p == nil || len(p.Blob) < 8 {
			continue
		}
		_ = os.WriteFile(filepath.Join(cacheDir, id+".bin"), p.Blob[:8], 0o644)
	}
	// When using cache-only warm, durable already holds blobs; still refresh files from facets.
	for id, facet := range facets {
		var buf [8]byte
		binary.BigEndian.PutUint64(buf[:], facet)
		_ = os.WriteFile(filepath.Join(cacheDir, id+".bin"), buf[:], 0o644)
		if durable[id] == nil {
			durable[id] = r2v.NewPack()
		}
		durable[id].Blob = append([]byte(nil), buf[:]...)
	}
	_ = WriteCacheArmTag(cacheDir, opts.Arm)

	primaries := map[string]bool{"a1": true, "b2": true, "g3": true}
	facetHexes := []string{}
	for _, er := range emitted {
		if primaries[er.TgtID] {
			facetHexes = append(facetHexes, er.FacetHex)
		}
	}
	sort.Strings(facetHexes)
	digest := DigestHex(facetHexes)

	bindPairs, bindOK := CacheBindPairs(durable, expanded)
	bindDigest := ""
	if bindOK {
		bindDigest = DigestHex(bindPairs)
	}

	doc := map[string]any{
		"rows": emitted,
		"summary": map[string]any{
			"ledger_digest": digest,
			"rows_total":    len(emitted),
			"span_band":     16,
		},
	}
	raw, _ := json.MarshalIndent(doc, "", "  ")
	_ = os.MkdirAll(opts.Out, 0o755)
	if err := os.WriteFile(filepath.Join(opts.Out, "conversion_ledger.json"), raw, 0o644); err != nil {
		return err
	}
	_ = WriteJournalTip(opts.Out, JournalTip{Arm: opts.Arm, Phase: opts.Phase, Digest: digest, Bind: bindDigest})

	traceDir := filepath.Join(opts.Out, "run_traces")
	_ = os.MkdirAll(traceDir, 0o755)
	trace := fmt.Sprintf("arm=%s phase=%s gate_first=%v cache_loaded=%d cache_dropped=%d salt=%x edges=%d targets=%s digest=%s\n",
		opts.Arm, opts.Phase, gateFirst, cacheLoaded, cacheDropped, salt, len(edges), strings.Join(expanded, ","), digest)
	return os.WriteFile(filepath.Join(traceDir, opts.Arm+"_"+opts.Phase+".trace"), []byte(trace), 0o644)
}

func DurableAgrees(outDir string, ledgerPath string) (bool, int, error) {
	raw, err := os.ReadFile(ledgerPath)
	if err != nil {
		return false, 0, err
	}
	var doc struct {
		Rows []t4w.EmittedRow `json:"rows"`
	}
	if err := json.Unmarshal(raw, &doc); err != nil {
		return false, 0, err
	}
	ok := true
	for _, r := range doc.Rows {
		b, err := os.ReadFile(filepath.Join(outDir, "cache", r.TgtID+".bin"))
		if err != nil || len(b) < 8 {
			ok = false
			continue
		}
		hexv := fmt.Sprintf("%016x", binary.BigEndian.Uint64(b[:8]))
		if hexv != r.FacetHex || r.Lag != 0 || r.SyncLabel != "settled" {
			ok = false
		}
	}
	return ok, len(doc.Rows), nil
}
