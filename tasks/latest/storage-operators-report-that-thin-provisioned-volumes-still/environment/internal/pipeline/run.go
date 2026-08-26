package pipeline

import (
	"crypto/sha256"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"time"

	"slotmgr/bind"
	"slotmgr/catalog"
	"slotmgr/relay"
	spanlane "slotmgr/range"
	"slotmgr/internal/store"
)

type PeerCfg struct {
	PeerTag string `toml:"peer_tag"`
	Path    string `toml:"path"`
}

type VolCfg struct {
	LogicalPath string `toml:"logical_path"`
	FieldPath   string `toml:"field_path"`
	Session     string `toml:"session"`
	RowUnits    int    `toml:"row_units"`
}

func loadJSON(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	return json.Unmarshal(b, &v)
}

func loadTOML(path string, v any) error {
	b, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	lines := strings.Split(string(b), "\n")
	switch ptr := v.(type) {
	case *VolCfg:
		loadVol := func(path string) {
			b, err := os.ReadFile(path)
			if err != nil {
				return
			}
			lines := strings.Split(string(b), "\n")
			for _, line := range lines {
			line = strings.TrimSpace(line)
			if line == "" || strings.HasPrefix(line, "#") {
				continue
			}
			parts := strings.SplitN(line, "=", 2)
			if len(parts) != 2 {
				continue
			}
			key := strings.TrimSpace(parts[0])
			val := strings.Trim(strings.TrimSpace(parts[1]), `"`)
			switch key {
			case "logical_path":
				ptr.LogicalPath = val
			case "field_path":
				ptr.FieldPath = val
			case "session":
				ptr.Session = val
			case "row_units":
				var n int
				_, _ = fmt.Sscanf(val, "%d", &n)
				ptr.RowUnits = n
			}
			}
		}
		loadVol(path)
		loadVol(strings.TrimSuffix(path, filepath.Base(path)) + "volume_paths.toml")
	case *[]PeerCfg:
		var cur PeerCfg
		for _, line := range lines {
			line = strings.TrimSpace(line)
			if strings.HasPrefix(line, "[[peer]]") {
				if cur.PeerTag != "" {
					*ptr = append(*ptr, cur)
				}
				cur = PeerCfg{}
				continue
			}
			if strings.HasPrefix(line, "peer_tag") {
				cur.PeerTag = strings.Trim(strings.TrimSpace(strings.SplitN(line, "=", 2)[1]), `"`)
			}
			if strings.HasPrefix(line, "path") {
				cur.Path = strings.Trim(strings.TrimSpace(strings.SplitN(line, "=", 2)[1]), `"`)
			}
		}
		if cur.PeerTag != "" {
			*ptr = append(*ptr, cur)
		}
	}
	return nil
}

func readPrefix(root string) ([]byte, error) {
	b, err := os.ReadFile(filepath.Join(root, "data", "seed_extents.bin"))
	if err != nil {
		return nil, err
	}
	if len(b) < 8 {
		return b, nil
	}
	return b[:8], nil
}

func bodyHex(prefix []byte, tick int) string {
	if tick < 1 {
		return ""
	}
	canon := append(append([]byte{}, prefix...), byte(tick&0xFF))
	sum := sha256.Sum256(canon)
	return hex.EncodeToString(sum[:])[:16]
}

func readPhase(root string) [2]byte {
	var phase [2]byte
	b, err := os.ReadFile(filepath.Join(root, "data", "window.phase"))
	if err != nil || len(b) < 2 {
		return phase
	}
	copy(phase[:], b[:2])
	return phase
}

func writePhase(root string, phase [2]byte) error {
	return os.WriteFile(filepath.Join(root, "data", "window.phase"), phase[:], 0o644)
}

func digestCeiling(outDir string) int {
	b, err := os.ReadFile(filepath.Join(outDir, "slot_map_digest.json"))
	if err != nil {
		return 0
	}
	var digest store.SlotDigest
	if json.Unmarshal(b, &digest) != nil {
		return 0
	}
	maxTick := 0
	for _, view := range digest.Views {
		if view.Epoch > maxTick {
			maxTick = view.Epoch
		}
	}
	return maxTick
}

func writeJSON(path string, v any) error {
	b, err := json.MarshalIndent(v, "", "  ")
	if err != nil {
		return err
	}
	return os.WriteFile(path, append(b, '\n'), 0o644)
}

func RunPass(root, outDir string, cycle int, appendMode bool) error {
	var peers []PeerCfg
	if err := loadTOML(filepath.Join(root, "config", "replay.toml"), &peers); err != nil {
		return err
	}
	var vcfg VolCfg
	if err := loadTOML(filepath.Join(root, "config", "volume.toml"), &vcfg); err != nil {
		return err
	}
	if vcfg.RowUnits < 1 {
		vcfg.RowUnits = 4096
	}

	suffix := string(rune('a' + cycle - 1))
	var arraySnap store.SlotSnap
	if err := loadJSON(filepath.Join(root, "fixtures", "array_slots_"+suffix+".json"), &arraySnap); err != nil {
		return err
	}
	var volSnap store.SlotSnap
	if err := loadJSON(filepath.Join(root, "fixtures", "volume_slots_"+suffix+".json"), &volSnap); err != nil {
		return err
	}
	var trim store.TrimEvt
	if err := loadJSON(filepath.Join(root, "fixtures", "trim_event.json"), &trim); err != nil {
		return err
	}
	var ratio store.UtilRatio
	if err := loadJSON(filepath.Join(root, "fixtures", "util_ratio.json"), &ratio); err != nil {
		return err
	}

	prefix, err := readPrefix(root)
	if err != nil {
		return err
	}

	priorMax := 0
	var priorRows []store.TranscriptRow
	if cycle >= 2 {
		priorMax = digestCeiling(outDir)
		prevPath := filepath.Join(outDir, "trim_transcript.json")
		if b, err := os.ReadFile(prevPath); err == nil {
			var prior store.TrimTranscript
			_ = json.Unmarshal(b, &prior)
			priorRows = prior.Rows
		}
	}

	phase := readPhase(root)
	ctx := &store.RunCtx{Pass: cycle, Append: appendMode, RowUnits: vcfg.RowUnits}
	aligned, _ := spanlane.AlignSpans(ctx, trim.Spans, root)

	freeDelta := 0
	if len(volSnap.Rows) > 0 && len(arraySnap.Rows) > 0 {
		freeDelta = volSnap.Rows[0].SlotsFree - arraySnap.Rows[0].ClearedUnits
		if freeDelta < 0 {
			freeDelta = 0
		}
	}

	baseTick := trim.Tick
	if cycle >= 2 {
		baseTick = spanlane.InheritLane(cycle, trim.Tick, priorRows, root)
		if priorMax > baseTick {
			baseTick = priorMax
		}
		baseTick++
	}

	var transcript []store.TranscriptRow
	var traces []store.TraceLine
	var viewDigests []store.Digest
	var fwdSkipped int
	var fwdApplied int

	for ord, peer := range peers {
		var slotRow store.SlotRow
		isArray := peer.PeerTag == "array_side"
		if isArray && len(arraySnap.Rows) > 0 {
			slotRow = arraySnap.Rows[0]
		} else if len(volSnap.Rows) > 0 {
			slotRow = volSnap.Rows[0]
		}
		if slotRow.PeerTag == "" {
			slotRow.PeerTag = peer.PeerTag
		}

		snap := &store.Snapshot{FreeDelta: freeDelta, PriorTick: priorMax, Pass: cycle, Span: spanlane.SpanBytes(aligned)}
		pview := catalog.PeerView(slotRow, isArray)
		dig, _ := catalog.BuildDigest(snap, pview, root)
		viewDigests = append(viewDigests, dig)

		laneTick := baseTick + ord
		if laneTick < dig.LaneTick {
			laneTick = dig.LaneTick
		}

		spanStart := 0
		spanEnd := vcfg.RowUnits
		stride := vcfg.RowUnits
		if len(aligned) > 0 {
			spanStart = aligned[0].Start
			spanEnd = aligned[0].End
			stride = aligned[0].Units
		}

		batch := store.Batch{
			Offset: spanStart, Len: spanEnd - spanStart,
			SlotWidth: vcfg.RowUnits, PeerTag: peer.PeerTag,
		}
		w := relay.NewMemWriter()
		stats, _ := relay.RouteBatch(w, batch)
		fwdApplied += stats.Forwarded
		fwdSkipped += stats.Skipped

		transcript = append(transcript, store.TranscriptRow{
			PeerID: peer.PeerTag, SpanStart: spanStart, SpanEnd: spanEnd,
			StrideUnits: stride, LaneTick: laneTick,
		})

		aVal := slotRow.ClearedUnits
		bVal := dig.Tick
		if !isArray {
			bVal = laneTick
		}
		traceTick := laneTick
		if !isArray && cycle >= 2 {
			traceTick = dig.Tick
		}
		traces = append(traces, store.TraceLine{Tick: traceTick, AVal: aVal, BVal: bVal})
		_ = w.Rows()
		_ = time.Millisecond
	}

	volRow := volSnap.Rows[0]
	arrayRow := arraySnap.Rows[0]
	snapFinal := &store.Snapshot{FreeDelta: freeDelta, PriorTick: priorMax, Pass: cycle, Span: spanlane.SpanBytes(aligned)}
	volDig, _ := catalog.BuildDigest(snapFinal, catalog.PeerView(volRow, false), root)
	viewTick := volDig.Tick
	if cycle >= 2 {
		if priorMax > 0 && viewTick <= priorMax {
			viewTick = priorMax + 1
		}
		if trim.ClearedUnits > 0 && viewTick <= trim.Tick {
			viewTick = trim.Tick + 1
		}
	}
	body := bodyHex(prefix, viewTick)

	slotsFree := volRow.SlotsFree
	if len(viewDigests) > 0 {
		slotsFree = viewDigests[0].SlotsFree
	}
	views := make([]store.ViewRow, 0, len(peers))
	for i, peer := range peers {
		peerSlots := slotsFree
		if i < len(viewDigests) {
			peerSlots = viewDigests[0].SlotsFree
		}
		views = append(views, store.ViewRow{
			PeerID: peer.PeerTag, BodyHex: body, Epoch: viewTick,
			LaneTick: transcript[i].LaneTick, SeriesNum: ratio.SeriesNum, SeriesDen: ratio.SeriesDen,
			SlotsFree: peerSlots, AppliedBytes: fwdApplied, SkippedBytes: fwdSkipped,
		})
	}
	_ = arrayRow

	conv := store.ConvergenceReport{Cycles: []store.CycleWin{{
		Cycle: cycle, AppliedBytes: fwdApplied, SkippedBytes: fwdSkipped,
	}}}

	if appendMode {
		prevPath := filepath.Join(outDir, "convergence_report.json")
		if prev, err := os.ReadFile(prevPath); err == nil {
			var existing store.ConvergenceReport
			_ = json.Unmarshal(prev, &existing)
			for _, c := range existing.Cycles {
				if c.Cycle == cycle {
					return nil
				}
			}
			conv.Cycles = append(existing.Cycles, conv.Cycles...)
		}
		tracePath := filepath.Join(outDir, "propagation_trace.jsonl")
		if b, err := os.ReadFile(tracePath); err == nil {
			var prior []store.TraceLine
			for _, line := range strings.Split(strings.TrimSpace(string(b)), "\n") {
				if line == "" {
					continue
				}
				var tl store.TraceLine
				if json.Unmarshal([]byte(line), &tl) == nil {
					prior = append(prior, tl)
				}
			}
			traces = append(prior, traces...)
		}
	}

	if err := os.MkdirAll(outDir, 0o755); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "trim_transcript.json"), store.TrimTranscript{Rows: transcript}); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "slot_map_digest.json"), store.SlotDigest{Views: views}); err != nil {
		return err
	}
	if err := writeJSON(filepath.Join(outDir, "convergence_report.json"), conv); err != nil {
		return err
	}
	f, err := os.Create(filepath.Join(outDir, "propagation_trace.jsonl"))
	if err != nil {
		return err
	}
	defer f.Close()
	for _, line := range traces {
		b, _ := json.Marshal(line)
		if _, err := f.Write(append(b, '\n')); err != nil {
			return err
		}
	}

	_ = bind.WriteSeq(root, cycle, viewTick)

	phase[0] = 1
	phase[1] = byte(cycle)
	return writePhase(root, phase)
}

func SessionID(root string) (string, error) {
	var vcfg VolCfg
	if err := loadTOML(filepath.Join(root, "config", "volume.toml"), &vcfg); err != nil {
		return "", err
	}
	return vcfg.Session, nil
}

func ViewsAligned(root, outDir string) (bool, error) {
	b, err := os.ReadFile(filepath.Join(outDir, "slot_map_digest.json"))
	if err != nil {
		return false, err
	}
	var digest store.SlotDigest
	if json.Unmarshal(b, &digest) != nil {
		return false, nil
	}
	if len(digest.Views) < 2 {
		return false, nil
	}
	epoch := digest.Views[0].Epoch
	slots := digest.Views[0].SlotsFree
	for _, v := range digest.Views[1:] {
		if v.Epoch != epoch || v.SlotsFree != slots {
			return false, nil
		}
		if v.SkippedBytes > 0 {
			return false, nil
		}
	}
	seqVal := bind.ReadSeq(root, false)
	if seqVal < epoch {
		return false, nil
	}
	return true, nil
}
