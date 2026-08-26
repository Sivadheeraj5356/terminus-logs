package replay

import (
	"encoding/json"
	"path/filepath"
	"sort"

	"orchard/canopyledger/accum"
	"orchard/canopyledger/audit"
	"orchard/canopyledger/config"
	"orchard/canopyledger/corrections"
	"orchard/canopyledger/emit"
	"orchard/canopyledger/manifest"
	"orchard/canopyledger/parse"
	"orchard/canopyledger/registry"
	"orchard/canopyledger/state"
	"orchard/canopyledger/util"
)

type Result struct {
	Ledger    []accum.Row
	Audit     []audit.Row
	State     state.ReplayState
	InputHash string
}

func Run(manifestPath, outDir, statePath string) error {
	m, err := manifest.Load(manifestPath)
	if err != nil {
		return err
	}
	hashParts, _, err := m.HashParts()
	if err != nil {
		return err
	}
	inputHash := state.InputHash(hashParts...)

	profilePath, err := m.Resolve(m.Profile)
	if err != nil {
		return err
	}
	site, err := config.LoadSettings(profilePath)
	if err != nil {
		return err
	}
	regPath, err := m.Resolve(m.SensorRegistry)
	if err != nil {
		return err
	}
	reg, err := registry.Load(regPath)
	if err != nil {
		return err
	}

	var feeds [][]parse.Reading
	var rawRows []parse.Reading
	for i, rel := range m.Readings {
		p, err := m.Resolve(rel)
		if err != nil {
			return err
		}
		rows, err := parse.LoadFeed(p, i)
		if err != nil {
			return err
		}
		feeds = append(feeds, rows)
		rawRows = append(rawRows, rows...)
	}

	var corrPaths []string
	for _, rel := range m.Corrections {
		p, err := m.Resolve(rel)
		if err != nil {
			return err
		}
		corrPaths = append(corrPaths, p)
	}

	winners, err := corrections.Collapse(feeds, corrPaths)
	if err != nil {
		return err
	}

	orig := corrections.OriginEpoch(feeds)
	res := build(site, reg, rawRows, winners, orig, inputHash, m.OrchardID)

	ledgerPath := filepath.Join(outDir, "s7_ledger.jsonl")
	auditPath := filepath.Join(outDir, "s7_audit.tsv")
	stateOut := filepath.Join(outDir, "replay_state.json")

	ledgerBytes, err := emit.EncodeReplayLedger(res.Ledger)
	if err != nil {
		return err
	}
	auditBytes := []byte(audit.FormatTSV(res.Audit))
	stJSON, err := json.MarshalIndent(res.State, "", "  ")
	if err != nil {
		return err
	}
	stJSON = append(stJSON, '\n')

	commit := map[string][]byte{
		ledgerPath: ledgerBytes,
		auditPath:  auditBytes,
		stateOut:   stJSON,
	}
	if statePath != "" && statePath != stateOut {
		commit[statePath] = stJSON
	}
	if err := util.AtomicCommit(commit); err != nil {
		return err
	}
	return nil
}

type effectiveReading struct {
	EpochSec  int64
	SensorID  string
	TempC     float64
	Quality   string
	ReadingID string
}

func build(
	site config.Settings,
	reg registry.Registry,
	raw []parse.Reading,
	winners []corrections.Record,
	orig map[string]struct {
		EpochSec int64
		SensorID string
	},
	inputHash, orchardID string,
) Result {
	base := config.EffectiveBase(site)
	envUnit := config.EffectiveIngestUnit(site)
	anchor := site.BucketAnchorEpoch
	if orchardID == "" {
		orchardID = site.OrchardID
	}

	type bkey struct {
		sensor string
		bucket int64
	}
	rawCounts := map[bkey]int{}
	for _, r := range raw {
		if !reg.Active(r.SensorID, r.EpochSec) {
			continue
		}
		b := replayWindowStart(r.EpochSec, anchor)
		rawCounts[bkey{r.SensorID, b}]++
	}

	var accepted []effectiveReading
	tombBuckets := map[bkey]int{}

	for _, w := range winners {
		if w.Delete {
			epoch := w.EpochSec
			sensor := w.SensorID
			if epoch == 0 {
				if o, ok := orig[w.ReadingID]; ok {
					epoch = o.EpochSec
					sensor = o.SensorID
				}
			}
			if epoch != 0 && sensor != "" {
				b := replayWindowStart(epoch, anchor)
				tombBuckets[bkey{sensor, b}]++
			}
			continue
		}
		if !reg.Active(w.SensorID, w.EpochSec) {
			continue
		}
		if w.Quality != "OK" {
			continue
		}
		e, ok := reg[w.SensorID]
		if !ok {
			continue
		}
		unit := envUnit
		if e.Unit != "" {
			unit = e.Unit
		}
		tempC := config.TempCelsius(unit, w.Temp) + e.OffsetC
		accepted = append(accepted, effectiveReading{
			EpochSec: w.EpochSec, SensorID: w.SensorID, TempC: tempC, Quality: w.Quality, ReadingID: w.ReadingID,
		})
	}

	sort.Slice(accepted, func(i, j int) bool {
		if accepted[i].EpochSec != accepted[j].EpochSec {
			return accepted[i].EpochSec < accepted[j].EpochSec
		}
		return accepted[i].SensorID < accepted[j].SensorID
	})

	ledgerAcc := map[bkey]*accum.Row{}
	acceptedCounts := map[bkey]int{}
	splitCounts := map[bkey]int{}
	prevEpoch := map[string]int64{}

	ensureRow := func(k bkey) *accum.Row {
		if ledgerAcc[k] == nil {
			ledgerAcc[k] = &accum.Row{
				OrchardID: orchardID, SensorID: k.sensor, BucketEpoch: k.bucket,
			}
		}
		return ledgerAcc[k]
	}

	for _, r := range accepted {
		bReading := replayWindowStart(r.EpochSec, anchor)
		prev := prevEpoch[r.SensorID]
		intervalStart := bReading
		if prev > 0 {
			intervalStart = prev
		}
		for _, seg := range splitInterval(intervalStart, r.EpochSec, anchor) {
			credit := accum.IntervalCredit(r.TempC, base, seg.hours)
			k := bkey{r.SensorID, seg.bucket}
			row := ensureRow(k)
			row.CreditHours += credit
			splitCounts[k]++
		}
		ensureRow(bkey{r.SensorID, bReading}).SampleCount++
		acceptedCounts[bkey{r.SensorID, bReading}]++
		prevEpoch[r.SensorID] = r.EpochSec
	}

	var ledger []accum.Row
	sensorSet := map[string]bool{}
	bucketSet := map[int64]bool{}
	for k, row := range ledgerAcc {
		row.CreditHours = util.Round4(row.CreditHours)
		ledger = append(ledger, *row)
		sensorSet[k.sensor] = true
		bucketSet[k.bucket] = true
	}
	sort.Slice(ledger, func(i, j int) bool {
		if ledger[i].BucketEpoch != ledger[j].BucketEpoch {
			return ledger[i].BucketEpoch < ledger[j].BucketEpoch
		}
		return ledger[i].SensorID < ledger[j].SensorID
	})

	auditKeys := map[bkey]bool{}
	for k := range rawCounts {
		auditKeys[k] = true
	}
	for k := range acceptedCounts {
		auditKeys[k] = true
	}
	for k := range tombBuckets {
		auditKeys[k] = true
	}
	for k := range splitCounts {
		auditKeys[k] = true
	}

	var auditRows []audit.Row
	for k := range auditKeys {
		auditRows = append(auditRows, audit.Row{
			OrchardID: orchardID, SensorID: k.sensor, BucketEpoch: k.bucket,
			RawSamples: rawCounts[k], AcceptedSamples: acceptedCounts[k],
			TombstonedSamples: tombBuckets[k], SplitSegments: splitCounts[k],
			InputHash: inputHash,
		})
	}
	sort.Slice(auditRows, func(i, j int) bool {
		if auditRows[i].BucketEpoch != auditRows[j].BucketEpoch {
			return auditRows[i].BucketEpoch < auditRows[j].BucketEpoch
		}
		return auditRows[i].SensorID < auditRows[j].SensorID
	})

	return Result{
		Ledger: ledger,
		Audit:  auditRows,
		State: state.ReplayState{
			StateVersion: state.StateVersion,
			InputHash:    inputHash,
			RowCount:     len(ledger),
			SensorCount:  len(sensorSet),
			BucketCount:  len(bucketSet),
		},
		InputHash: inputHash,
	}
}

type segment struct {
	bucket int64
	hours  float64
}

func splitInterval(start, end, anchor int64) []segment {
	if end <= start {
		return nil
	}
	const day int64 = 86400
	var out []segment
	pos := start
	for pos < end {
		b := replayWindowStart(pos, anchor)
		bend := b + day
		segEnd := end
		if segEnd > bend {
			segEnd = bend
		}
		hours := float64(segEnd-pos) / 3600.0
		out = append(out, segment{bucket: b, hours: hours})
		pos = segEnd
	}
	return out
}

func replayWindowStart(epoch, anchor int64) int64 {
	const day int64 = 86400
	delta := epoch - anchor
	q := delta / day
	if delta < 0 && delta%day != 0 {
		q--
	}
	return anchor + q*day
}
