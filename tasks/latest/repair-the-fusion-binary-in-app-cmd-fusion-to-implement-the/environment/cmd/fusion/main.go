package main

import (
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"sort"
	"strconv"
	"strings"
)

type manifest struct {
	Name          string    `json:"name"`
	Labels        []string  `json:"labels"`
	ScaleDen      int       `json:"scale_den"`
	ScaleNum      []int     `json:"scale_num"`
	Zero          []int     `json:"zero"`
	ClipMin       []int     `json:"clip_min"`
	ClipMax       []int     `json:"clip_max"`
	SensorOrder   []int     `json:"sensor_order"`
	ZoneShift     []int     `json:"zone_shift"`
	Bias          []int     `json:"bias_milli"`
	Weights       [][]int   `json:"weights_milli"`
	ZoneBias      [][]int   `json:"zone_bias_milli"`
	LoadBias      [][]int   `json:"load_bias_milli"`
	AnchorBias    []int     `json:"anchor_bias_milli"`
	ShardBias     [][]int   `json:"shard_bias_milli"`
	QualityBias   []int     `json:"quality_bias_milli"`
	QualityWeight [][]int   `json:"quality_weights_milli"`
	TimeBias      [][]int   `json:"time_bias_milli"`
	SpanBias      [][]int   `json:"span_bias_milli"`
	TrendWeight   [][]int   `json:"trend_weights_milli"`
	DriftBias     []int     `json:"drift_bias_milli"`
	MixBias       []int     `json:"mix_bias_milli"`
	MedianWeight  [][]int   `json:"median_milli"`
	PairTerms     [][][]int `json:"pair_terms"`
	Source        string    `json:"-"`
	Filename      string    `json:"-"`
	RankScore     int       `json:"-"`
	Drift         int       `json:"-"`
	Anchor        int       `json:"-"`
	Weight        int       `json:"-"`
}

type frame struct {
	id     uint32
	zone   byte
	minute int
	values []int
	quality byte
	batch  string
	mix    int
}

type prediction struct {
	id     uint32
	batch  string
	minute int
	zone   int
	event  string
	margin int
}

type batchStat struct {
	rows       int
	mix        int
	mixSet     bool
	zoneCounts [8]int
	medians    []int
	minuteMin  int
	minuteMax  int
	minuteMed  int
	minSet     bool
}

type auditManifest struct {
	Name      string `json:"name"`
	RankScore int    `json:"rank_score"`
	Drift     int    `json:"drift"`
	Anchor    string `json:"anchor"`
	Weight    int    `json:"weight"`
}

type auditBatch struct {
	Batch         string `json:"batch"`
	Rows          int    `json:"rows"`
	BatchMix      int    `json:"batch_mix"`
	MinuteMin     int    `json:"minute_min"`
	MinuteMax     int    `json:"minute_max"`
	MinuteMedian  int    `json:"minute_median"`
	ZoneCounts    []int  `json:"zone_counts"`
	QualityCounts []int  `json:"quality_counts"`
}

type auditDoc struct {
	Manifests []auditManifest `json:"manifests"`
	Rows      int             `json:"rows"`
	Batches   []auditBatch    `json:"batches"`
	SHA       string          `json:"events_sha256"`
}

func main() {
	telemetryDir := flag.String("telemetry-dir", "/app/telemetry", "telemetry directory")
	calDir := flag.String("calibration-dir", "/app/calibration", "calibration directory")
	probe := flag.String("probe", "/app/probe/driftprobe", "probe")
	probeBatch := flag.String("probe-batch", "/app/telemetry/public.cfr", "probe batch")
	out := flag.String("out", "/app/output/events.tsv", "events")
	auditOut := flag.String("audit-out", "/app/output/audit.json", "audit")
	flag.Parse()
	if err := run(*telemetryDir, *calDir, *probe, *probeBatch, *out, *auditOut); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

func run(telemetryDir, calDir, probe, probeBatch, out, auditOut string) error {
	manifests, err := loadManifests(calDir)
	if err != nil {
		return err
	}
	selected, err := chooseManifests(manifests, probe, probeBatch)
	if err != nil {
		return err
	}
	if err := validateEnsemble(selected); err != nil {
		return err
	}
	frames, err := loadFrames(telemetryDir)
	if err != nil {
		return err
	}
	stats := map[string]map[string]batchStat{}
	for _, m := range selected {
		stats[m.Source] = buildStats(frames, m)
	}
	preds := make([]prediction, 0, len(frames))
	for _, f := range frames {
		preds = append(preds, classify(f, selected, stats))
	}
	tsv := renderTSV(preds)
	audit, err := renderAudit(selected, frames, tsv)
	if err != nil {
		return err
	}
	return writeBothAtomic(out, tsv, auditOut, audit)
}

func loadManifests(dir string) ([]manifest, error) {
	files, err := filepath.Glob(filepath.Join(dir, "*.json"))
	if err != nil {
		return nil, err
	}
	sort.Strings(files)
	var out []manifest
	for _, file := range files {
		data, err := os.ReadFile(file)
		if err != nil {
			return nil, err
		}
		var m manifest
		if err := json.Unmarshal(data, &m); err != nil {
			return nil, err
		}
		if strings.TrimSpace(m.Name) == "" {
			m.Name = strings.TrimSuffix(filepath.Base(file), filepath.Ext(file))
		}
		m.Source = file
		m.Filename = filepath.Base(file)
		if err := validateManifest(m); err != nil {
			return nil, fmt.Errorf("%s: %w", file, err)
		}
		out = append(out, m)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no calibration manifests")
	}
	return out, nil
}

func validateManifest(m manifest) error {
	classes := len(m.Labels)
	features := len(m.ScaleNum)
	if classes == 0 || features == 0 || m.ScaleDen <= 0 {
		return fmt.Errorf("bad manifest shape")
	}
	if len(m.Zero) != features || len(m.ClipMin) != features || len(m.ClipMax) != features || len(m.SensorOrder) != features {
		return fmt.Errorf("bad feature arrays")
	}
	if len(m.Bias) != classes || len(m.DriftBias) != classes || len(m.MixBias) != classes || len(m.AnchorBias) != classes || len(m.QualityBias) != classes || len(m.Weights) != classes || len(m.QualityWeight) != classes || len(m.TrendWeight) != classes || len(m.MedianWeight) != classes || len(m.PairTerms) != classes {
		return fmt.Errorf("bad class arrays")
	}
	if len(m.ZoneShift) != 8 || len(m.ZoneBias) != 8 || len(m.LoadBias) != 8 || len(m.ShardBias) != 8 || len(m.SpanBias) != 8 || len(m.TimeBias) != 16 {
		return fmt.Errorf("bad zone arrays")
	}
	for _, idx := range m.SensorOrder {
		if idx < 0 || idx >= features {
			return fmt.Errorf("bad sensor order")
		}
	}
	for i := range m.Weights {
		if len(m.Weights[i]) != features || len(m.QualityWeight[i]) != features || len(m.TrendWeight[i]) != features || len(m.MedianWeight[i]) != features {
			return fmt.Errorf("bad weight width")
		}
		for _, term := range m.PairTerms[i] {
			if len(term) != 3 || term[0] < 0 || term[1] < 0 || term[0] >= features || term[1] >= features {
				return fmt.Errorf("bad pair term")
			}
		}
	}
	for _, row := range m.ZoneBias {
		if len(row) != classes {
			return fmt.Errorf("bad zone bias width")
		}
	}
	for _, row := range m.LoadBias {
		if len(row) != classes {
			return fmt.Errorf("bad load bias width")
		}
	}
	for _, row := range m.ShardBias {
		if len(row) != classes {
			return fmt.Errorf("bad shard bias width")
		}
	}
	for _, row := range m.SpanBias {
		if len(row) != classes {
			return fmt.Errorf("bad span bias width")
		}
	}
	for _, row := range m.TimeBias {
		if len(row) != classes {
			return fmt.Errorf("bad time bias width")
		}
	}
	return nil
}

func validateEnsemble(ms []manifest) error {
	if len(ms) == 0 {
		return fmt.Errorf("empty ensemble")
	}
	for _, m := range ms[1:] {
		if m.ScaleDen != ms[0].ScaleDen || len(m.Labels) != len(ms[0].Labels) {
			return fmt.Errorf("selected manifests are incompatible")
		}
		for i := range m.Labels {
			if m.Labels[i] != ms[0].Labels[i] {
				return fmt.Errorf("selected manifest labels differ")
			}
		}
	}
	return nil
}

var rankRe = regexp.MustCompile(`rank_score=(-?[0-9]+)`)
var driftRe = regexp.MustCompile(`drift=(-?[0-9]+)`)
var anchorRe = regexp.MustCompile(`anchor=([0-9a-fA-F]{8})`)

func chooseManifests(ms []manifest, probe, batch string) ([]manifest, error) {
	for i := range ms {
		cmd := exec.Command(probe, "--manifest", ms[i].Source, "--batch", batch)
		data, err := cmd.CombinedOutput()
		if err != nil {
			return nil, fmt.Errorf("probe %s: %v: %s", ms[i].Source, err, strings.TrimSpace(string(data)))
		}
		text := string(data)
		rankMatch := rankRe.FindStringSubmatch(text)
		driftMatch := driftRe.FindStringSubmatch(text)
		anchorMatch := anchorRe.FindStringSubmatch(text)
		if rankMatch == nil || driftMatch == nil || anchorMatch == nil {
			return nil, fmt.Errorf("bad probe output for %s: %s", ms[i].Source, strings.TrimSpace(text))
		}
		rank, _ := strconv.Atoi(rankMatch[1])
		drift, _ := strconv.Atoi(driftMatch[1])
		anchor, err := strconv.ParseInt(anchorMatch[1], 16, 32)
		if err != nil {
			return nil, err
		}
		ms[i].RankScore = rank
		ms[i].Drift = drift
		ms[i].Anchor = int(anchor)
	}
	sort.Slice(ms, func(i, j int) bool {
		if ms[i].RankScore == ms[j].RankScore {
			return ms[i].Filename < ms[j].Filename
		}
		return ms[i].RankScore < ms[j].RankScore
	})
	limit := 2
	if len(ms) < 2 {
		limit = len(ms)
	}
	selected := append([]manifest{}, ms[:limit]...)
	weights := []int{4, 2}
	for i := range selected {
		selected[i].Weight = weights[i]
	}
	return selected, nil
}

func loadFrames(dir string) ([]frame, error) {
	files, err := filepath.Glob(filepath.Join(dir, "*.cfr"))
	if err != nil {
		return nil, err
	}
	sort.Strings(files)
	var out []frame
	for _, file := range files {
		batch := strings.TrimSuffix(filepath.Base(file), filepath.Ext(file))
		frames, err := readCFR(file, batch)
		if err != nil {
			return nil, err
		}
		out = append(out, frames...)
	}
	if len(out) == 0 {
		return nil, fmt.Errorf("no telemetry frames")
	}
	return out, nil
}

func readCFR(path, batch string) ([]frame, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	if len(data) >= 10 && string(data[:4]) == "ALS2" {
		return readSegmentedCFR(data, path, batch)
	}
	return readFlatCFR(data, path, batch)
}

func readFlatCFR(data []byte, path, batch string) ([]frame, error) {
	if len(data) < 17 || string(data[:4]) != "ALT1" || data[4] != 1 {
		return nil, fmt.Errorf("bad cfr header: %s", path)
	}
	dim := int(data[5])
	flags := data[6]
	width := int(data[7])
	count := int(binary.LittleEndian.Uint16(data[8:10]))
	mask := data[10]
	if dim <= 0 || data[11] != byte((dim*19+count+int(mask)+int(flags)+width)&0xff) {
		return nil, fmt.Errorf("bad cfr header check: %s", path)
	}
	if len(data) < 17 {
		return nil, fmt.Errorf("short cfr file: %s", path)
	}
	if string(data[len(data)-5:len(data)-3]) != "AL" {
		return nil, fmt.Errorf("bad cfr footer magic: %s", path)
	}
	footer := data[len(data)-5:]
	if footer[4] != byte((sumBytes(footer[:4])+int(mask)+count)&0xff) {
		return nil, fmt.Errorf("bad cfr footer: %s", path)
	}
	mix := int(binary.LittleEndian.Uint16(footer[2:4]))
	out, pos, _, err := readFrameBlock(data, 12, count, dim, flags, width, mask, batch, mix, 0, path)
	if err != nil {
		return nil, err
	}
	if pos+5 != len(data) {
		return nil, fmt.Errorf("bad cfr footer length: %s", path)
	}
	return out, nil
}

func readSegmentedCFR(data []byte, path, batch string) ([]frame, error) {
	if len(data) < 15 || data[4] != 2 {
		return nil, fmt.Errorf("bad segmented cfr header: %s", path)
	}
	segmentCount := int(data[5])
	total := int(binary.LittleEndian.Uint16(data[6:8]))
	containerMask := data[8]
	if data[9] != byte((segmentCount*37+total+int(containerMask))&0xff) {
		return nil, fmt.Errorf("bad segmented cfr header check: %s", path)
	}
	if string(data[len(data)-5:len(data)-3]) != "AS" {
		return nil, fmt.Errorf("bad segmented cfr footer magic: %s", path)
	}
	footer := data[len(data)-5:]
	if footer[4] != byte((sumBytes(footer[:4])+int(containerMask)+segmentCount+total)&0xff) {
		return nil, fmt.Errorf("bad segmented cfr footer: %s", path)
	}
	mix := int(binary.LittleEndian.Uint16(footer[2:4]))
	pos := 10
	minute := 0
	out := make([]frame, 0, total)
	for segmentIndex := 0; segmentIndex < segmentCount; segmentIndex++ {
		if pos+7 > len(data)-5 {
			return nil, fmt.Errorf("short segmented cfr segment: %s", path)
		}
		flags := data[pos]
		width := int(data[pos+1])
		dim := int(data[pos+2])
		mask := data[pos+3]
		count := int(binary.LittleEndian.Uint16(data[pos+4 : pos+6]))
		if dim <= 0 || data[pos+6] != byte((dim*19+count+int(mask)+int(flags)+width+segmentIndex)&0xff) {
			return nil, fmt.Errorf("bad segmented cfr segment check: %s", path)
		}
		block, next, nextMinute, err := readFrameBlock(data, pos+7, count, dim, flags, width, mask, batch, mix, minute, path)
		if err != nil {
			return nil, err
		}
		out = append(out, block...)
		pos = next
		minute = nextMinute
	}
	if len(out) != total || pos+5 != len(data) {
		return nil, fmt.Errorf("bad segmented cfr length: %s", path)
	}
	return out, nil
}

func readFrameBlock(data []byte, pos int, count int, dim int, flags byte, width int, mask byte, batch string, mix int, minute int, path string) ([]frame, int, int, error) {
	out := make([]frame, 0, count)
	for i := 0; i < count; i++ {
		if pos+7 > len(data) {
			return nil, pos, minute, fmt.Errorf("short cfr frame prefix: %s", path)
		}
		id := binary.LittleEndian.Uint32(data[pos : pos+4])
		zone := data[pos+4]
		delta := zigzag16(binary.LittleEndian.Uint16(data[pos+5 : pos+7]))
		seedLen := 0
		seed := byte(0)
		if flags&0x20 != 0 {
			if pos+8 > len(data) {
				return nil, pos, minute, fmt.Errorf("short cfr lane seed: %s", path)
			}
			seedLen = 1
			seed = data[pos+7]
		}
		laneStart := pos + 7 + seedLen
		laneMask := effectiveMask(mask, flags, id, zone, dim, seed)
		laneLen, err := laneLength(data, laneStart, dim, flags, width, laneMask)
		if err != nil {
			return nil, pos, minute, fmt.Errorf("%s: %w", path, err)
		}
		qualityLen := 0
		if width&0x20 != 0 {
			qualityLen = 1
		}
		need := 4 + 1 + 2 + seedLen + laneLen + qualityLen + 1
		if pos+need > len(data) {
			return nil, pos, minute, fmt.Errorf("short cfr frame: %s", path)
		}
		rec := data[pos : pos+need]
		if rec[len(rec)-1] != byte((sumBytes(rec[:len(rec)-1])+int(mask))&0xff) {
			return nil, pos, minute, fmt.Errorf("bad cfr frame check: %s", path)
		}
		lane := append([]byte{}, rec[7+seedLen:7+seedLen+laneLen]...)
		quality := byte(0)
		if qualityLen != 0 {
			quality = rec[7+seedLen+laneLen]
			if int(quality)>>dim != 0 {
				return nil, pos, minute, fmt.Errorf("quality mask outside sensor dimension: %s", path)
			}
		}
		if flags&0x01 != 0 {
			for j := range lane {
				lane[j] ^= laneMask
			}
		}
		raw, err := decodeLane(lane, dim, id, zone, flags, width)
		if err != nil {
			return nil, pos, minute, fmt.Errorf("%s: %w", path, err)
		}
		values := make([]int, dim)
		predictor := int(zone) - 3
		for j := 0; j < dim; j++ {
			v := raw[j]
			if flags&0x02 != 0 {
				predictor += v
				v = predictor
			}
			values[j] = v
		}
		minute += delta
		out = append(out, frame{id: id, zone: zone, minute: minute, values: values, quality: quality, batch: batch, mix: mix})
		pos += need
	}
	return out, pos, minute, nil
}

func laneLength(data []byte, laneStart, dim int, flags byte, width int, mask byte) (int, error) {
	if flags&0x80 != 0 && flags&0x08 == 0 {
		return 0, fmt.Errorf("index-table flag without sparse flag")
	}
	if flags&0x04 != 0 {
		if packedWidth(width) <= 0 || packedWidth(width) > 8 {
			return 0, fmt.Errorf("bad packed width")
		}
	} else if width&^0x20 != 0 {
		return 0, fmt.Errorf("unexpected width for byte lane")
	}
	if flags&0x08 == 0 {
		if flags&0x04 != 0 {
			return (dim*packedWidth(width) + 7) / 8, nil
		}
		return dim, nil
	}
	if flags&0x80 != 0 {
		if laneStart >= len(data) {
			return 0, fmt.Errorf("short explicit sparse descriptor")
		}
		present := data[laneStart]
		if flags&0x01 != 0 {
			present ^= mask
		}
		desc := 1 + int(present)
		if laneStart+desc > len(data) {
			return 0, fmt.Errorf("short explicit sparse indexes")
		}
		if flags&0x04 != 0 {
			return desc + (int(present)*packedWidth(width)+7)/8, nil
		}
		return desc + int(present), nil
	}
	desc := (dim + 7) / 8
	if laneStart+desc > len(data) {
		return 0, fmt.Errorf("short sparse bitmap")
	}
	bitmap := append([]byte{}, data[laneStart:laneStart+desc]...)
	if flags&0x01 != 0 {
		for i := range bitmap {
			bitmap[i] ^= mask
		}
	}
	present := 0
	for j := 0; j < dim; j++ {
		if bitmap[j/8]&(1<<uint(j&7)) != 0 {
			present++
		}
	}
	if flags&0x04 != 0 {
		return desc + (present*packedWidth(width)+7)/8, nil
	}
	return desc + present, nil
}

func decodeLane(lane []byte, dim int, id uint32, zone byte, flags byte, width int) ([]int, error) {
	raw := make([]int, dim)
	if flags&0x08 != 0 {
		var indexes []int
		var payload []byte
		if flags&0x80 != 0 {
			if len(lane) == 0 {
				return nil, fmt.Errorf("short explicit sparse descriptor")
			}
			present := int(lane[0])
			if len(lane) < 1+present {
				return nil, fmt.Errorf("short explicit sparse indexes")
			}
			for _, b := range lane[1 : 1+present] {
				idx := int(b)
				if idx < 0 || idx >= dim {
					return nil, fmt.Errorf("bad explicit sparse index")
				}
				indexes = append(indexes, idx)
			}
			payload = lane[1+present:]
		} else {
			desc := (dim + 7) / 8
			if len(lane) < desc {
				return nil, fmt.Errorf("short sparse bitmap")
			}
			bitmap := lane[:desc]
			order := numericOrder(dim)
			if flags&0x10 != 0 {
				order = laneOrder(dim, zone)
			}
			for _, idx := range order {
				if bitmap[idx/8]&(1<<uint(idx&7)) != 0 {
					indexes = append(indexes, idx)
				}
			}
			payload = lane[desc:]
		}
		if flags&0x40 != 0 {
			payload = rotateRight(payload, rotation(id, zone, dim, len(payload)))
		}
		if flags&0x04 != 0 && width&0x40 != 0 {
			payload = nibbleSwap(payload)
		}
		values, err := payloadValues(payload, len(indexes), flags, width)
		if err != nil {
			return nil, err
		}
		for i, idx := range indexes {
			raw[idx] = values[i]
		}
		return raw, nil
	}
	if flags&0x40 != 0 {
		lane = rotateRight(lane, rotation(id, zone, dim, len(lane)))
	}
	if flags&0x04 != 0 && width&0x40 != 0 {
		lane = nibbleSwap(lane)
	}
	values, err := payloadValues(lane, dim, flags, width)
	if err != nil {
		return nil, err
	}
	if flags&0x10 != 0 {
		for i, idx := range laneOrder(dim, zone) {
			raw[idx] = values[i]
		}
	} else {
		copy(raw, values)
	}
	return raw, nil
}

func payloadValues(payload []byte, count int, flags byte, width int) ([]int, error) {
	if flags&0x04 != 0 {
		return unpackSigned(payload, count, width)
	}
	if len(payload) != count {
		return nil, fmt.Errorf("bad byte payload length")
	}
	out := make([]int, count)
	for i, b := range payload {
		out[i] = int(int8(b))
	}
	return out, nil
}

func unpackSigned(data []byte, count int, width int) ([]int, error) {
	bitWidth := packedWidth(width)
	out := make([]int, count)
	acc := 0
	bits := 0
	pos := 0
	mask := (1 << bitWidth) - 1
	sign := 1 << (bitWidth - 1)
	for i := 0; i < count; i++ {
		for bits < bitWidth {
			if pos >= len(data) {
				return nil, fmt.Errorf("short packed payload")
			}
			acc |= int(data[pos]) << bits
			bits += 8
			pos++
		}
		v := acc & mask
		acc >>= bitWidth
		bits -= bitWidth
		if width&0x80 != 0 {
			v = (v >> 1) ^ -(v & 1)
		} else if v&sign != 0 {
			v -= 1 << bitWidth
		}
		out[i] = v
	}
	return out, nil
}

func qualityFlagsFor(f frame, m manifest) []bool {
	zone := int(f.zone) & 7
	out := make([]bool, len(m.ScaleNum))
	for j := range out {
		source := (m.SensorOrder[j] + m.ZoneShift[zone]) % len(f.values)
		out[j] = f.quality&(1<<uint(source)) != 0
	}
	return out
}

func centeredFor(f frame, m manifest) []int {
	zone := int(f.zone) & 7
	qflags := qualityFlagsFor(f, m)
	out := make([]int, len(m.ScaleNum))
	for j := range out {
		source := (m.SensorOrder[j] + m.ZoneShift[zone]) % len(f.values)
		if qflags[j] {
			out[j] = 0
			continue
		}
		v := f.values[source]
		if v < m.ClipMin[j] {
			v = m.ClipMin[j]
		}
		if v > m.ClipMax[j] {
			v = m.ClipMax[j]
		}
		out[j] = v - m.Zero[j]
	}
	return out
}

func buildStats(frames []frame, m manifest) map[string]batchStat {
	values := map[string][][]int{}
	minutes := map[string][]int{}
	stats := map[string]batchStat{}
	for _, f := range frames {
		st := stats[f.batch]
		st.rows++
		st.zoneCounts[int(f.zone)&7]++
		if !st.mixSet {
			st.mix = f.mix
			st.mixSet = true
		}
		if !st.minSet || f.minute < st.minuteMin {
			st.minuteMin = f.minute
		}
		if !st.minSet || f.minute > st.minuteMax {
			st.minuteMax = f.minute
		}
		st.minSet = true
		stats[f.batch] = st
		if _, ok := values[f.batch]; !ok {
			values[f.batch] = make([][]int, len(m.ScaleNum))
		}
		minutes[f.batch] = append(minutes[f.batch], f.minute)
		for j, v := range centeredFor(f, m) {
			values[f.batch][j] = append(values[f.batch][j], v)
		}
	}
	for batch, perFeature := range values {
		st := stats[batch]
		st.medians = make([]int, len(perFeature))
		for j, vals := range perFeature {
			sort.Ints(vals)
			st.medians[j] = vals[(len(vals)-1)/2]
		}
		sort.Ints(minutes[batch])
		st.minuteMed = minutes[batch][(len(minutes[batch])-1)/2]
		stats[batch] = st
	}
	return stats
}

func classify(f frame, ms []manifest, stats map[string]map[string]batchStat) prediction {
	labels := ms[0].Labels
	combined := make([]int, len(labels))
	totalWeight := 0
	for _, m := range ms {
		totalWeight += m.Weight
		score := scoreOne(f, m, stats[m.Source][f.batch])
		for c, v := range score {
			combined[c] += m.Weight * v
		}
	}
	best, second := 0, -1
	for i := 1; i < len(combined); i++ {
		if combined[i] > combined[best] {
			second = best
			best = i
		} else if i != best && (second < 0 || combined[i] > combined[second] || (combined[i] == combined[second] && i < second)) {
			second = i
		}
	}
	if second < 0 {
		second = best
	}
	return prediction{id: f.id, batch: f.batch, minute: f.minute, zone: int(f.zone) & 7, event: labels[best], margin: roundDiv(combined[best]-combined[second], ms[0].ScaleDen*totalWeight)}
}

func scoreOne(f frame, m manifest, st batchStat) []int {
	zone := int(f.zone) & 7
	shard := int(((f.id >> 4) ^ uint32(zone) ^ uint32(m.Anchor&7)) & 7)
	centered := centeredFor(f, m)
	qflags := qualityFlagsFor(f, m)
	qcount := 0
	for _, flag := range qflags {
		if flag {
			qcount++
		}
	}
	minuteDelta := f.minute - st.minuteMed
	if minuteDelta < -64 {
		minuteDelta = -64
	}
	if minuteDelta > 64 {
		minuteDelta = 64
	}
	timePhase := (minuteDelta + zone*3 + (m.Anchor & 15)) & 15
	spanBucket := (st.minuteMax - st.minuteMin) & 7
	scores := make([]int, len(m.Labels))
	for c := range m.Labels {
		score := (m.Bias[c] + m.ZoneBias[zone][c] + m.ShardBias[shard][c]) * m.ScaleDen
		score += m.Drift * m.DriftBias[c] * m.ScaleDen
		anchorTerm := ((m.Anchor >> uint((c*7)%17)) & 31) - 16
		score += anchorTerm * m.AnchorBias[c] * m.ScaleDen
		mixTerm := ((f.mix >> uint((zone+c)&7)) & 15) - 8
		score += mixTerm * m.MixBias[c] * m.ScaleDen
		loadTerm := st.zoneCounts[zone]*8 - st.rows
		score += loadTerm * m.LoadBias[zone][c] * m.ScaleDen
		score += m.SpanBias[spanBucket][c] * m.ScaleDen
		score += m.TimeBias[timePhase][c] * m.ScaleDen
		score += qcount * m.QualityBias[c] * m.ScaleDen
		for j := range centered {
			score += m.Weights[c][j] * centered[j] * m.ScaleNum[j]
			score += m.MedianWeight[c][j] * (centered[j]-st.medians[j]) * m.ScaleNum[j]
			score += m.TrendWeight[c][j] * centered[j] * minuteDelta
			if qflags[j] {
				score += m.QualityWeight[c][j] * m.ScaleDen
			}
		}
		for _, term := range m.PairTerms[c] {
			score += term[2] * centered[term[0]] * centered[term[1]]
		}
		scores[c] = score
	}
	return scores
}

func renderTSV(preds []prediction) []byte {
	sort.Slice(preds, func(i, j int) bool {
		if preds[i].id == preds[j].id {
			return preds[i].batch < preds[j].batch
		}
		return preds[i].id < preds[j].id
	})
	var b strings.Builder
	b.WriteString("frame_id\tbatch\tminute\tzone\tevent\tmargin_milli\n")
	for _, p := range preds {
		fmt.Fprintf(&b, "%08x\t%s\t%d\t%d\t%s\t%d\n", p.id, p.batch, p.minute, p.zone, p.event, p.margin)
	}
	return []byte(b.String())
}

func renderAudit(ms []manifest, frames []frame, tsv []byte) ([]byte, error) {
	doc := auditDoc{Rows: len(frames)}
	for _, m := range ms {
		doc.Manifests = append(doc.Manifests, auditManifest{Name: m.Name, RankScore: m.RankScore, Drift: m.Drift, Anchor: fmt.Sprintf("%08x", uint32(m.Anchor)), Weight: m.Weight})
	}
	namesMap := map[string]bool{}
	for _, f := range frames {
		namesMap[f.batch] = true
	}
	var names []string
	for name := range namesMap {
		names = append(names, name)
	}
	sort.Strings(names)
	for _, name := range names {
		ab := auditBatch{Batch: name, ZoneCounts: make([]int, 8), QualityCounts: make([]int, 8)}
		mixSet := false
		var minutes []int
		for _, f := range frames {
			if f.batch != name {
				continue
			}
			ab.Rows++
			ab.ZoneCounts[int(f.zone)&7]++
			minutes = append(minutes, f.minute)
			for sensor := 0; sensor < len(ab.QualityCounts) && sensor < len(f.values); sensor++ {
				if f.quality&(1<<uint(sensor)) != 0 {
					ab.QualityCounts[sensor]++
				}
			}
			if !mixSet {
				ab.BatchMix = f.mix
				mixSet = true
			}
		}
		sort.Ints(minutes)
		ab.MinuteMin = minutes[0]
		ab.MinuteMax = minutes[len(minutes)-1]
		ab.MinuteMedian = minutes[(len(minutes)-1)/2]
		doc.Batches = append(doc.Batches, ab)
	}
	sum := sha256.Sum256(tsv)
	doc.SHA = fmt.Sprintf("%x", sum[:])
	data, err := json.MarshalIndent(doc, "", "  ")
	if err != nil {
		return nil, err
	}
	return append(data, '\n'), nil
}

func writeBothAtomic(outPath string, outData []byte, auditPath string, auditData []byte) error {
	outTmp, err := writeTempSibling(outPath, outData)
	if err != nil {
		return err
	}
	auditTmp, err := writeTempSibling(auditPath, auditData)
	if err != nil {
		os.Remove(outTmp)
		return err
	}
	outBackup, outHadBackup, err := moveAside(outPath)
	if err != nil {
		os.Remove(outTmp)
		os.Remove(auditTmp)
		return err
	}
	auditBackup, auditHadBackup, err := moveAside(auditPath)
	if err != nil {
		restorePath(outPath, outBackup, outHadBackup)
		os.Remove(outTmp)
		os.Remove(auditTmp)
		return err
	}
	if err := os.Rename(outTmp, outPath); err != nil {
		restorePath(auditPath, auditBackup, auditHadBackup)
		restorePath(outPath, outBackup, outHadBackup)
		os.Remove(outTmp)
		os.Remove(auditTmp)
		return err
	}
	if err := os.Rename(auditTmp, auditPath); err != nil {
		_ = os.Rename(outPath, outTmp)
		restorePath(outPath, outBackup, outHadBackup)
		restorePath(auditPath, auditBackup, auditHadBackup)
		os.Remove(outTmp)
		os.Remove(auditTmp)
		return err
	}
	if outHadBackup {
		os.Remove(outBackup)
	}
	if auditHadBackup {
		os.Remove(auditBackup)
	}
	return nil
}

func writeTempSibling(path string, data []byte) (string, error) {
	if err := os.MkdirAll(filepath.Dir(path), 0755); err != nil {
		return "", err
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, data, 0644); err != nil {
		return "", err
	}
	return tmp, nil
}

func moveAside(path string) (string, bool, error) {
	if _, err := os.Lstat(path); err != nil {
		if os.IsNotExist(err) {
			return "", false, nil
		}
		return "", false, err
	}
	backup := path + ".bak"
	_ = os.Remove(backup)
	if err := os.Rename(path, backup); err != nil {
		return "", false, err
	}
	return backup, true, nil
}

func restorePath(path, backup string, hadBackup bool) {
	if !hadBackup {
		_ = os.Remove(path)
		return
	}
	_ = os.Remove(path)
	_ = os.Rename(backup, path)
}

func zigzag16(v uint16) int {
	u := int(v)
	return (u >> 1) ^ -(u & 1)
}

func packedWidth(width int) int {
	if width&0xC0 != 0 {
		return width & 0x0F
	}
	return width
}

func sumBytes(data []byte) int {
	n := 0
	for _, b := range data {
		n += int(b)
	}
	return n
}

func effectiveMask(mask byte, flags byte, frameID uint32, zone byte, dim int, seed byte) byte {
	if flags&0x20 == 0 {
		return mask
	}
	return byte((int(mask) ^ int(seed) ^ int((frameID>>7)&0xff) ^ ((int(zone)&7)*29)) & 0xff)
}

func laneOrder(dim int, zone byte) []int {
	out := make([]int, dim)
	start := int(zone) % dim
	step := 1
	for i := 0; i < dim; i++ {
		out[i] = (start + i*step) % dim
	}
	return out
}

func numericOrder(dim int) []int {
	out := make([]int, dim)
	for i := range out {
		out[i] = i
	}
	return out
}

func rotation(frameID uint32, zone byte, dim int, n int) int {
	if n <= 1 {
		return 0
	}
	return int((frameID + (frameID >> 8) + uint32(zone)*13 + uint32(dim)*5) % uint32(n))
}

func rotateRight(data []byte, amount int) []byte {
	if len(data) == 0 {
		return data
	}
	amount %= len(data)
	if amount == 0 {
		return data
	}
	out := make([]byte, 0, len(data))
	out = append(out, data[len(data)-amount:]...)
	out = append(out, data[:len(data)-amount]...)
	return out
}

func nibbleSwap(data []byte) []byte {
	out := make([]byte, len(data))
	for i, b := range data {
		out[i] = ((b & 0x0f) << 4) | (b >> 4)
	}
	return out
}

func roundDiv(n, d int) int {
	if n >= 0 {
		return (n + d/2) / d
	}
	return -((-n + d/2) / d)
}
