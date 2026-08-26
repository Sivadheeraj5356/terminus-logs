package driver

import (
	"context"
	"encoding/json"
	"os"
	"path/filepath"
	"sort"
	"strings"

	"burstverify/emit"
	"burstverify/internal/io"
	"burstverify/internal/sink"
	"burstverify/internal/spool"
	"burstverify/recyclegate"
	"burstverify/journalspan"
	"burstverify/relay"
	"burstverify/runtime"
	"burstverify/store"
)

const (
	resumePath  = "/app/state/resume.offset"
	segmentPath = "/app/state/segment.cache.json"
)

type Event struct {
	Kind        string `json:"kind"`
	WriterEpoch string `json:"writer_epoch,omitempty"`
	ReaderEpoch string `json:"reader_epoch,omitempty"`
	Bytes       int    `json:"bytes,omitempty"`
}

type FixtureSpec struct {
	SinkMode string  `json:"sink_mode"`
	PipeCap  int     `json:"pipe_cap"`
	Events   []Event `json:"events"`
}

func pickWriter(mode string, cap int, lc *relay.Lifecycle) io.Writer {
	if mode == "redirect" {
		return &sink.RedirectSink{}
	}
	return &sink.WrapSink{Capacity: cap, Lifecycle: lc}
}

func appendTrace(tracePath, label, phase, writer, reader string, ledger spool.Ledger) error {
	return journalspan.AppendTrace(tracePath, journalspan.LedgerTraceLine{
		FixtureLabel: label,
		Phase:        phase,
		Observed:     ledger.ObservedBytes,
		Pending:      ledger.PendingBytes,
		WriterEpoch:  writer,
		ReaderEpoch:  reader,
		SpanMix:      journalspan.SpanMixCheckpoint(writer, reader, ledger),
	})
}

func appendJournal(journalPath, label, phase string, ledger spool.Ledger) error {
	return journalspan.AppendJournal(journalPath, label, phase, ledger.ObservedBytes, ledger.PendingBytes)
}

func runWave(ctx context.Context, writer io.Writer, total int, lim emit.Limits, ledger *spool.Ledger, label, tracePath, journalPath, writerEpoch, readerEpoch string) error {
	slices, err := emit.PlanSlices(ctx, total, lim)
	if err != nil {
		return err
	}
	for _, sl := range slices {
		n, term, err := writer.WriteChunk(sl.Size)
		if err != nil {
			return err
		}
		st, err := runtime.GuardTerm(ctx, term, runtime.RunState{})
		if err != nil {
			return err
		}
		if term.PipeClosed {
			if st.Fatal {
				ledger.Add(n)
				return nil
			}
			ledger.StagePending(n)
			break
		}
		ledger.Add(n)
	}
	return nil
}

func runFixture(label string, spec FixtureSpec, tracePath, journalPath, completionManifestPath string, lc *relay.Lifecycle) (journalspan.ReportRow, error) {
	ctx := context.Background()
	ledger := spool.NewLedger()
	recoveryStore := recyclegate.NewStore(&ledger)
	writerEpoch := "0000"
	readerEpoch := "0000"
	_ = completionManifestPath

	for _, ev := range spec.Events {
		switch ev.Kind {
		case "seed":
			writerEpoch = strings.ToLower(ev.WriterEpoch)
			readerEpoch = strings.ToLower(ev.ReaderEpoch)
			lc.ReaderEpoch = readerEpoch
			if err := store.ApplyResume(resumePath, label, readerEpoch, &ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			var cached int
			store.ApplySegment(segmentPath, label, readerEpoch, &cached)
			if cached > 0 {
				ledger.ObservedBytes = cached
			}
			if err := appendTrace(tracePath, label, "seed", writerEpoch, readerEpoch, ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			if err := appendJournal(journalPath, label, "seed", ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
		case "recycle":
			if err := appendTrace(tracePath, label, "recycle_before", writerEpoch, readerEpoch, ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			if err := appendJournal(journalPath, label, "recycle_before", ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			res, err := recyclegate.ReplayCheckpoint(ctx, recoveryStore, recyclegate.Limits{Recycle: true})
			if err != nil {
				return journalspan.ReportRow{}, err
			}
			ledger = res.Ledger
			recoveryStore = recyclegate.NewStore(&ledger)
			relay.Recycle(lc, strings.ToLower(ev.ReaderEpoch))
			readerEpoch = lc.ReaderEpoch
			writerEpoch = readerEpoch
			if err := appendTrace(tracePath, label, "recycle_after", writerEpoch, readerEpoch, ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			if err := appendJournal(journalPath, label, "recycle_after", ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
		case "wave":
			lim := emit.Limits{PipeCap: spec.PipeCap}
			w := pickWriter(spec.SinkMode, spec.PipeCap, lc)
			if err := runWave(ctx, w, ev.Bytes, lim, &ledger, label, tracePath, journalPath, writerEpoch, readerEpoch); err != nil {
				return journalspan.ReportRow{}, err
			}
			if err := appendTrace(tracePath, label, "wave_end", writerEpoch, readerEpoch, ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
			if err := appendJournal(journalPath, label, "wave_end", ledger); err != nil {
				return journalspan.ReportRow{}, err
			}
		}
	}
	_ = store.SaveSegment(segmentPath, label, readerEpoch, ledger.ObservedBytes)
	return journalspan.BuildRecord(label, writerEpoch, readerEpoch, ledger), nil
}

func DriveAll(fixturesDir, tracePath, journalPath, completionManifestPath string) ([]journalspan.ReportRow, error) {
	if tracePath != "" {
		if err := journalspan.ResetTrace(tracePath); err != nil {
			return nil, err
		}
	}
	if journalPath != "" {
		if err := journalspan.ResetJournal(journalPath); err != nil {
			return nil, err
		}
	}
	_ = completionManifestPath
	entries, err := os.ReadDir(fixturesDir)
	if err != nil {
		return nil, err
	}
	var names []string
	for _, ent := range entries {
		if ent.IsDir() || !strings.HasSuffix(ent.Name(), ".json") {
			continue
		}
		names = append(names, ent.Name())
	}
	sort.Strings(names)
	lc := &relay.Lifecycle{}
	runs := make([]journalspan.ReportRow, 0, len(names))
	for _, name := range names {
		raw, err := os.ReadFile(filepath.Join(fixturesDir, name))
		if err != nil {
			return nil, err
		}
		var spec FixtureSpec
		if err := json.Unmarshal(raw, &spec); err != nil {
			return nil, err
		}
		label := strings.TrimSuffix(name, ".json")
		row, err := runFixture(label, spec, tracePath, journalPath, completionManifestPath, lc)
		if err != nil {
			return nil, err
		}
		runs = append(runs, row)
	}
	return runs, nil
}
