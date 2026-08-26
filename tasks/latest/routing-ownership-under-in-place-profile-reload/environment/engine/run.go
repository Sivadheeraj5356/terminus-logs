package engine

import (
	"encoding/json"
	"os"
	"path/filepath"

	"linkenv/emit"
	"linkenv/lse"
	"linkenv/pub"
	"linkenv/qtn"
	"linkenv/rcv"
	"linkenv/reg"
	"linkenv/shim"
	"linkenv/wal"
)

type Profile struct {
	Name     string       `json:"name"`
	Slots    []string     `json:"slots"`
	Manager  []reg.RowRec `json:"manager_rows"`
	Catch    []reg.RowRec `json:"catch_rows"`
	ChurnSeq int          `json:"churn_seq"`
}

type Store struct {
	Root     string
	Registry []reg.RowRec
	Tags     map[string]uint8
	Feed     *lse.FeedState
	Tx       *pub.TxState
	Gen      uint64
	Qtn      *qtn.Ledger
}

func LoadProfile(topoDir, name string) (*Profile, error) {
	path := filepath.Join(topoDir, name+".json")
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var p Profile
	if err := json.Unmarshal(raw, &p); err != nil {
		return nil, err
	}
	p.Name = name
	return &p, nil
}

func LoadProfiles(topoDir string, names []string) ([]*Profile, error) {
	out := make([]*Profile, 0, len(names))
	for _, n := range names {
		p, err := LoadProfile(topoDir, n)
		if err != nil {
			return nil, err
		}
		out = append(out, p)
	}
	return out, nil
}

func NewStore(root string) *Store {
	return &Store{
		Root: root,
		Tags: map[string]uint8{},
		Feed: lse.NewFeedState(),
		Tx:   pub.NewTx(),
		Qtn:  qtn.NewLedger(),
	}
}

func (s *Store) Persist() error {
	return s.persist()
}

func (s *Store) persist() error {
	if err := os.MkdirAll(s.Root, 0o755); err != nil {
		return err
	}
	type snap struct {
		Registry []reg.RowRec
		Tags     map[string]uint8
		Feed     *lse.FeedState
		Tx       *pub.TxState
		Gen      uint64
		Qtn      *qtn.Ledger
	}
	raw, err := json.Marshal(snap{
		Registry: s.Registry,
		Tags:     s.Tags,
		Feed:     s.Feed,
		Tx:       s.Tx,
		Gen:      s.Gen,
		Qtn:      s.Qtn,
	})
	if err != nil {
		return err
	}
	return os.WriteFile(filepath.Join(s.Root, "snap.json"), raw, 0o644)
}

func (s *Store) loadSnap() error {
	raw, err := os.ReadFile(filepath.Join(s.Root, "snap.json"))
	if err != nil {
		return err
	}
	type snap struct {
		Registry []reg.RowRec
		Tags     map[string]uint8
		Feed     *lse.FeedState
		Tx       *pub.TxState
		Gen      uint64
		Qtn      *qtn.Ledger
	}
	var sn snap
	if err := json.Unmarshal(raw, &sn); err != nil {
		return err
	}
	s.Registry = sn.Registry
	s.Tags = sn.Tags
	s.Feed = sn.Feed
	s.Tx = sn.Tx
	s.Gen = sn.Gen
	if sn.Qtn != nil {
		s.Qtn = sn.Qtn
	} else {
		s.Qtn = qtn.NewLedger()
	}
	return nil
}

func tagMap(rows []reg.RowRec) map[string]uint8 {
	m := map[string]uint8{}
	for _, r := range rows {
		m[r.Key] = r.Class
	}
	return m
}

func dynRowsFromFeed(st *lse.FeedState, prof *Profile) []reg.RowRec {
	var out []reg.RowRec
	for _, r := range prof.Manager {
		if st.ActivePref == nil || !st.ActivePref[r.Prefix] {
			continue
		}
		row := r
		row.Class = reg.ClassDyn
		out = append(out, row)
	}
	return out
}

func (s *Store) admitForeign(foreignPath string) error {
	items, err := shim.LoadInject(foreignPath)
	if err != nil {
		return err
	}
	for _, it := range items {
		if qtn.RegistryHasKey(s.Registry, it.Row.Key) || s.Qtn.HasKey(it.Row.Key) {
			continue
		}
		fence := s.Feed.Fence
		if it.AdmitFence != nil {
			fence = *it.AdmitFence
		}
		s.Qtn.Admit(it.Row, fence)
	}
	return nil
}

func (s *Store) promotedInject() []reg.RowRec {
	return s.Qtn.Promote(s.Feed.Epoch, s.Feed.Fence)
}

func (s *Store) buildColdRegistry(prof *Profile) {
	inject := s.promotedInject()
	s.Registry = append([]reg.RowRec{}, inject...)
	for _, r := range prof.Catch {
		row := r
		row.Class = reg.ClassCatch
		s.Registry = append(s.Registry, row)
	}
	s.Registry = append(s.Registry, dynRowsFromFeed(s.Feed, prof)...)
	s.Tags = tagMap(s.Registry)
}

func (s *Store) planCommit(prof *Profile, outDir string, rows []reg.RowRec) error {
	s.Gen++
	s.Tx.Planned[s.Gen] = append([]reg.RowRec{}, rows...)
	s.Tx.OpenGen = s.Gen
	if err := wal.Append(s.Root, wal.Frame{Gen: s.Gen, Sealed: false, Rows: rows}); err != nil {
		return err
	}
	_ = emit.AppendJournal(outDir, emit.MakeJournalLine("plan", s.Gen, s.Gen-1, prof.Name))
	view, err := pub.SealTx(s.Tx, s.Gen)
	if err != nil {
		return err
	}
	s.Registry = view.Rows
	s.Tags = tagMap(s.Registry)
	s.Tx.Committed[s.Gen] = append([]reg.RowRec{}, s.Registry...)
	_ = wal.SealLatest(s.Root, s.Gen)
	_ = emit.AppendJournal(outDir, emit.MakeJournalLine("commit", s.Gen, s.Gen, prof.Name))
	return nil
}

func (s *Store) ColdBoot(prof *Profile, foreignPath, feedPath, outDir string) error {
	s.Feed = lse.NewFeedState()
	s.Qtn = qtn.NewLedger()
	events, err := lse.LoadEvents(feedPath)
	if err != nil {
		return err
	}
	for _, ev := range events {
		lse.BumpFeed(s.Feed, ev)
	}
	if err := s.admitForeign(foreignPath); err != nil {
		return err
	}
	s.buildColdRegistry(prof)
	if err := s.planCommit(prof, outDir, s.Registry); err != nil {
		return err
	}
	fp := emit.Fingerprint(s.Registry)
	if err := emit.WriteFib(outDir, s.Registry, fp); err != nil {
		return err
	}
	if err := s.writeObs(prof, outDir, s.Gen, s.Gen); err != nil {
		return err
	}
	return s.persist()
}

func (s *Store) ApplyProfile(prof *Profile, foreignPath, feedPath, outDir string) error {
	if err := s.loadSnap(); err != nil {
		return err
	}
	events, err := lse.LoadEvents(feedPath)
	if err != nil {
		return err
	}
	for _, ev := range events {
		if ev.Seq > prof.ChurnSeq {
			continue
		}
		lse.BumpFeed(s.Feed, ev)
	}
	if err := s.admitForeign(foreignPath); err != nil {
		return err
	}
	inject := s.promotedInject()
	prior := append([]reg.RowRec{}, s.Registry...)
	prior = append(prior, inject...)
	want := dynRowsFromFeed(s.Feed, prof)
	for _, r := range prof.Catch {
		row := r
		row.Class = reg.ClassCatch
		want = append(want, row)
	}
	merged, err := reg.ReconcileApply(prior, want, s.Tags)
	if err != nil {
		return err
	}
	if err := s.planCommit(prof, outDir, merged); err != nil {
		return err
	}
	fp := emit.Fingerprint(s.Registry)
	if err := emit.WriteFib(outDir, s.Registry, fp); err != nil {
		return err
	}
	if err := s.persist(); err != nil {
		return err
	}
	return s.writeObs(prof, outDir, s.Gen, s.Gen-1)
}

func (s *Store) Recover(outDir, profileName string) error {
	if err := s.loadSnap(); err != nil {
		s.Feed = lse.NewFeedState()
		s.Tx = pub.NewTx()
		s.Qtn = qtn.NewLedger()
	}
	if s.Feed == nil {
		s.Feed = lse.NewFeedState()
	}
	if s.Tx == nil {
		s.Tx = pub.NewTx()
	}
	if s.Qtn == nil {
		s.Qtn = qtn.NewLedger()
	}
	tip := rcv.LoadSealedTip(s.Root, s.Tx)
	if tip.Gen == 0 {
		return os.ErrNotExist
	}
	s.Gen = tip.Gen
	s.Registry = append([]reg.RowRec{}, tip.Rows...)
	s.Tags = rcv.TagMap(s.Registry)
	if s.Tx.Committed == nil {
		s.Tx.Committed = map[uint64][]reg.RowRec{}
	}
	s.Tx.Committed[s.Gen] = append([]reg.RowRec{}, s.Registry...)
	s.Tx.OpenGen = s.Gen
	fp := emit.Fingerprint(s.Registry)
	if err := emit.WriteFib(outDir, s.Registry, fp); err != nil {
		return err
	}
	prof, err := LoadProfile("/app/data/topology_w3", profileName)
	if err != nil {
		prof = &Profile{Name: profileName, Slots: []string{"lc0"}}
	}
	if err := s.writeObs(prof, outDir, s.Gen, s.Gen); err != nil {
		return err
	}
	_ = emit.AppendJournal(outDir, emit.MakeJournalLine("recover", s.Gen, s.Gen, profileName))
	return s.persist()
}

func (s *Store) writeObs(prof *Profile, outDir string, planned, committed uint64) error {
	probes := make([]emit.LinkSlot, 0, len(prof.Slots))
	for _, slot := range prof.Slots {
		probes = append(probes, emit.LinkSlot{
			SlotID:    slot,
			CarrierUp: lse.ProbeCarrier(slot),
			MirrorGen: planned,
		})
	}
	return emit.WriteLinkStatus(outDir, probes)
}
