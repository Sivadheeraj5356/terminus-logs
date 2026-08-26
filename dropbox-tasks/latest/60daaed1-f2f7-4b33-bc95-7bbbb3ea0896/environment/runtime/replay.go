package main

import (
    "bufio"
    "crypto/sha1"
    "encoding/hex"
    "encoding/json"
    "os"
    "path/filepath"
    "sync"
    "time"
)

type grantRecord struct {
    User       string `json:"user"`
    Role       string `json:"role"`
    LastSeq    int64  `json:"last_seq"`
    LastUpdate int64  `json:"last_update"`
}

type replaySnapshot struct {
    Version     int                    `json:"version"`
    Seq         int64                  `json:"seq"`
    Grants      map[string]grantRecord `json:"grants"`
    AliasRecent map[string]int64       `json:"alias_recent"`
    RouteSeq    map[string]int64       `json:"route_seq"`
    Corruptions int64                  `json:"corruptions"`
}

type replayEvent struct {
    Type      string `json:"type"`
    Canonical string `json:"canonical"`
    RawPath   string `json:"raw_path"`
    User      string `json:"user"`
    Role      string `json:"role"`
    Seq       int64  `json:"seq"`
    At        int64  `json:"at"`
}

type ReplayStore struct {
    mu           sync.Mutex
    journalPath  string
    snapshotPath string
    seq          int64
    grants       map[string]grantRecord
    aliasRecent  map[string]int64
    routeSeq     map[string]int64
    corruptions  int64
}

func NewReplayStore(stateDir string) (*ReplayStore, error) {
    if err := os.MkdirAll(stateDir, 0o755); err != nil {
        return nil, err
    }
    rs := &ReplayStore{
        journalPath:  filepath.Join(stateDir, "auth_journal.log"),
        snapshotPath: filepath.Join(stateDir, "auth_snapshot.json"),
        grants:       map[string]grantRecord{},
        aliasRecent:  map[string]int64{},
        routeSeq:     map[string]int64{},
    }
    if err := rs.load(); err != nil {
        return nil, err
    }
    return rs, nil
}

func aliasKey(rawPath, canonical string) string {
    h := sha1.Sum([]byte(canonicalDispatchPath(rawPath) + "|" + canonical))
    return hex.EncodeToString(h[:])
}

func (r *ReplayStore) load() error {
    if b, err := os.ReadFile(r.snapshotPath); err == nil && len(b) > 0 {
        var snap replaySnapshot
        if json.Unmarshal(b, &snap) == nil {
            r.seq = snap.Seq
            r.corruptions = snap.Corruptions
            if snap.Grants != nil {
                r.grants = snap.Grants
            }
            if snap.AliasRecent != nil {
                r.aliasRecent = snap.AliasRecent
            }
            if snap.RouteSeq != nil {
                r.routeSeq = snap.RouteSeq
            }
        }
    }

    f, err := os.Open(r.journalPath)
    if err != nil {
        if os.IsNotExist(err) {
            return nil
        }
        return err
    }
    defer f.Close()

    s := bufio.NewScanner(f)
    for s.Scan() {
        line := s.Bytes()
        if len(line) == 0 {
            continue
        }
        var ev replayEvent
        if err := json.Unmarshal(line, &ev); err != nil {
            r.corruptions++
            continue
        }
        if ev.Type != "grant" {
            continue
        }
        if ev.Seq > r.seq {
            r.seq = ev.Seq
        }
        r.grants[ev.Canonical] = grantRecord{User: ev.User, Role: ev.Role, LastSeq: ev.Seq, LastUpdate: ev.At}
        if ev.RawPath != "" {
            r.aliasRecent[aliasKey(ev.RawPath, ev.Canonical)] = ev.At
        }
    }
    return s.Err()
}

func (r *ReplayStore) appendEvent(ev replayEvent) error {
    f, err := os.OpenFile(r.journalPath, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0o644)
    if err != nil {
        return err
    }
    defer f.Close()
    enc := json.NewEncoder(f)
    return enc.Encode(ev)
}

func (r *ReplayStore) persistSnapshot() error {
    snap := replaySnapshot{Version: 3, Seq: r.seq, Grants: r.grants, AliasRecent: r.aliasRecent, RouteSeq: r.routeSeq, Corruptions: r.corruptions}
    b, err := json.MarshalIndent(snap, "", "  ")
    if err != nil {
        return err
    }
    return os.WriteFile(r.snapshotPath, b, 0o644)
}

func (r *ReplayStore) RecordGrant(rawPath, canonical string, who tokenRecord) error {
    r.mu.Lock()
    defer r.mu.Unlock()
    r.seq++
    now := time.Now().Unix()
    rec := grantRecord{User: who.User, Role: who.Role, LastSeq: r.seq, LastUpdate: now}
    r.grants[canonical] = rec
    r.routeSeq[canonical] = r.seq
    r.aliasRecent[aliasKey(rawPath, canonical)] = now
    ev := replayEvent{Type: "grant", RawPath: rawPath, Canonical: canonical, User: who.User, Role: who.Role, Seq: r.seq, At: now}
    if err := r.appendEvent(ev); err != nil {
        return err
    }
    if r.seq%3 == 0 {
        return r.persistSnapshot()
    }
    return nil
}

func (r *ReplayStore) LatestGrant(canonical string) (grantRecord, bool) {
    r.mu.Lock()
    defer r.mu.Unlock()
    g, ok := r.grants[canonical]
    return g, ok
}

func (r *ReplayStore) HasRecentAlias(rawPath, canonical string, maxAgeSec int64) bool {
    r.mu.Lock()
    defer r.mu.Unlock()
    at, ok := r.aliasRecent[aliasKey(rawPath, canonical)]
    if !ok {
        return false
    }
    return time.Now().Unix()-at <= maxAgeSec
}

func (r *ReplayStore) Stats() map[string]any {
    r.mu.Lock()
    defer r.mu.Unlock()
    route := map[string]int64{}
    for k, v := range r.routeSeq {
        route[k] = v
    }
    return map[string]any{
        "seq":          r.seq,
        "grant_routes": len(r.grants),
        "aliases":      len(r.aliasRecent),
        "corruptions":  r.corruptions,
        "route_seq":    route,
    }
}
