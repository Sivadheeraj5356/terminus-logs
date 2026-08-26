package main

import (
    "bytes"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "errors"
    "fmt"
    "io"
    "os"
    "os/exec"
    "path/filepath"
    "sort"
    "strconv"
    "strings"
)

type CursorEvent struct {
    Seq               int    `json:"seq"`
    Event             string `json:"event"`
    PartitionID       string `json:"partition_id,omitempty"`
    CursorStart       string `json:"cursor_start,omitempty"`
    CursorEnd         string `json:"cursor_end,omitempty"`
    PrevCursor        string `json:"prev_cursor,omitempty"`
    Action            string `json:"action,omitempty"`
    OmissionReason    string `json:"omission_reason,omitempty"`
    RollbackWindow    string `json:"rollback_window,omitempty"`
    ServiceGeneration string `json:"service_generation,omitempty"`
    ReloadID          string `json:"reload_id,omitempty"`
    ReplacesPartition string `json:"replaces_partition_id,omitempty"`
    Reason            string `json:"reason,omitempty"`
}

type PartitionEntry struct {
    PartitionID       string `json:"partition_id"`
    Sequence          int    `json:"sequence"`
    Path              string `json:"path"`
    Status            string `json:"status"`
    CursorStart       string `json:"cursor_start"`
    CursorEnd         string `json:"cursor_end"`
    PrevCursor        string `json:"prev_cursor"`
    DigestHex         string `json:"digest_hex"`
    OmissionReason    string `json:"omission_reason,omitempty"`
    OmissionDigestHex string `json:"omission_digest_hex,omitempty"`
}

type Manifest struct {
    SchemaVersion     int              `json:"schema_version"`
    BundleID          string           `json:"bundle_id"`
    ServiceUnit       string           `json:"service_unit"`
    ReloadGeneration  string           `json:"reload_generation"`
    PartitionEntries  []PartitionEntry `json:"partition_entries"`
    Signer            Signer           `json:"signer"`
}

type Signer struct {
    KeyID          string `json:"key_id"`
    SignedAt       string `json:"signed_at"`
    LineageHashHex string `json:"lineage_hash_hex"`
}

type ExportState struct {
    SchemaVersion        int      `json:"schema_version"`
    ServiceUnit          string   `json:"service_unit"`
    Status               string   `json:"status"`
    SucceededAfter       string   `json:"succeeded_after_partition"`
    HighWaterCursor      string   `json:"high_water_cursor"`
    LastCompleteEventSeq int      `json:"last_complete_event_seq"`
    ResumeGeneration     string   `json:"resume_generation"`
    Lineage              []string `json:"lineage"`
    OmittedPartitions    []string `json:"omitted_partitions"`
}

type LedgerRow struct {
    PartitionID       string `json:"partition_id"`
    Sequence          int    `json:"sequence"`
    Status            string `json:"status"`
    CursorStart       string `json:"cursor_start"`
    CursorEnd         string `json:"cursor_end"`
    PrevCursor        string `json:"prev_cursor"`
    DigestHex         string `json:"digest_hex"`
    OmissionReason    string `json:"omission_reason"`
    OmissionDigestHex string `json:"omission_digest_hex"`
    ServiceGeneration string `json:"service_generation"`
    BatchID           string `json:"batch_id"`
    Terminal          int    `json:"terminal"`
}

type Report struct {
    SchemaVersion       int              `json:"schema_version"`
    BundleID            string           `json:"bundle_id"`
    Status              string           `json:"status"`
    ServiceUnit         string           `json:"service_unit"`
    HighWaterCursor     string           `json:"high_water_cursor"`
    ExportedPartitions  []string         `json:"exported_partitions"`
    OmittedPartitions   []string         `json:"omitted_partitions"`
    LineageHashHex      string           `json:"lineage_hash_hex"`
    ManifestDigestHex   string           `json:"manifest_digest_hex"`
    SignatureHex        string           `json:"signature_hex"`
    AuthorityMismatches []string         `json:"authority_mismatches"`
    Partitions          []PartitionEntry `json:"partitions"`
}

type Workspace struct {
    Root      string
    Trace     []CursorEvent
    Manifest  Manifest
    State     ExportState
    Ledger    []LedgerRow
    Expected  []PartitionEntry
    Exported  []string
    Omitted   []string
    Mismatches []string
}

func main() {
    if len(os.Args) < 2 {
        usage(2)
    }
    cmd := os.Args[1]
    switch cmd {
    case "export":
        root, out := parseRootOut(os.Args[2:])
        ws, err := loadWorkspace(root)
        if err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
        if err := writeExport(ws, out); err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
    case "verify":
        root, out := parseRootOut(os.Args[2:])
        ws, err := loadWorkspace(root)
        if err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
        if err := writeExport(ws, out); err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
        if len(ws.Mismatches) != 0 {
            for _, item := range ws.Mismatches {
                fmt.Fprintln(os.Stderr, item)
            }
            os.Exit(1)
        }
    case "legacy-verify":
        root := parseRootOnly(os.Args[2:])
        if err := verifyLegacy(root); err != nil {
            fmt.Fprintln(os.Stderr, err)
            os.Exit(1)
        }
    default:
        usage(2)
    }
}

func usage(code int) {
    fmt.Fprintln(os.Stderr, "usage: rotlogctl export|verify --root DIR --out DIR; rotlogctl legacy-verify --root DIR")
    os.Exit(code)
}

func parseRootOut(args []string) (string, string) {
    root, out := "", ""
    for i := 0; i < len(args); i++ {
        switch args[i] {
        case "--root":
            i++
            if i < len(args) { root = args[i] }
        case "--out":
            i++
            if i < len(args) { out = args[i] }
        default:
            usage(2)
        }
    }
    if root == "" || out == "" { usage(2) }
    return root, out
}

func parseRootOnly(args []string) string {
    root := ""
    for i := 0; i < len(args); i++ {
        switch args[i] {
        case "--root":
            i++
            if i < len(args) { root = args[i] }
        default:
            usage(2)
        }
    }
    if root == "" { usage(2) }
    return root
}

func loadWorkspace(root string) (*Workspace, error) {
    trace, err := readTrace(filepath.Join(root, "runtime", "cursor_trace.jsonl"))
    if err != nil { return nil, err }
    manifest, err := readJSON[Manifest](filepath.Join(root, "manifests", "bundle_manifest.json"))
    if err != nil { return nil, err }
    state, err := readJSON[ExportState](filepath.Join(root, "state", "export_state.json"))
    if err != nil { return nil, err }
    ledger, err := readLedger(filepath.Join(root, "state", "export_ledger.sqlite"))
    if err != nil { return nil, err }
    ws := &Workspace{Root: root, Trace: trace, Manifest: manifest, State: state, Ledger: ledger}
    ws.Expected = expectedEntries(root, trace)
    ws.Exported, ws.Omitted = partitionSets(ws.Expected)
    ws.Mismatches = collectMismatches(ws)
    return ws, nil
}

func readTrace(path string) ([]CursorEvent, error) {
    raw, err := os.ReadFile(path)
    if err != nil { return nil, err }
    var out []CursorEvent
    for i, line := range strings.Split(string(raw), "\n") {
        line = strings.TrimSpace(line)
        if line == "" { continue }
        var ev CursorEvent
        if err := json.Unmarshal([]byte(line), &ev); err != nil {
            return nil, fmt.Errorf("%s:%d: %w", path, i+1, err)
        }
        out = append(out, ev)
    }
    sort.Slice(out, func(i, j int) bool { return out[i].Seq < out[j].Seq })
    return out, nil
}

func readJSON[T any](path string) (T, error) {
    var out T
    raw, err := os.ReadFile(path)
    if err != nil { return out, err }
    err = json.Unmarshal(raw, &out)
    return out, err
}

func readLedger(db string) ([]LedgerRow, error) {
    query := `select partition_id, sequence, status, cursor_start, cursor_end, prev_cursor, digest_hex, coalesce(omission_reason,'') as omission_reason, coalesce(omission_digest_hex,'') as omission_digest_hex, service_generation, batch_id, terminal from checkpoint order by sequence;`
    cmd := exec.Command("sqlite3", "-json", db, query)
    raw, err := cmd.CombinedOutput()
    if err != nil { return nil, fmt.Errorf("sqlite ledger query failed: %v: %s", err, string(raw)) }
    if len(bytes.TrimSpace(raw)) == 0 { return nil, nil }
    var rows []LedgerRow
    if err := json.Unmarshal(raw, &rows); err != nil { return nil, fmt.Errorf("sqlite json decode: %w: %s", err, string(raw)) }
    return rows, nil
}

func expectedEntries(root string, trace []CursorEvent) []PartitionEntry {
    var out []PartitionEntry
    for _, ev := range trace {
        if ev.PartitionID == "" || (ev.Action != "export" && ev.Action != "omit") { continue }
        path := filepath.ToSlash(filepath.Join("logs", ev.PartitionID+".journal"))
        digest := sha256File(filepath.Join(root, path))
        entry := PartitionEntry{
            PartitionID: ev.PartitionID,
            Sequence: ev.Seq,
            Path: path,
            Status: ev.Action,
            CursorStart: ev.CursorStart,
            CursorEnd: ev.CursorEnd,
            PrevCursor: ev.PrevCursor,
            DigestHex: digest,
        }
        if ev.Action == "omit" {
            entry.OmissionReason = ev.OmissionReason
            entry.OmissionDigestHex = omissionDigest(entry)
        }
        out = append(out, entry)
    }
    return out
}

func sha256File(path string) string {
    f, err := os.Open(path)
    if err != nil { return "" }
    defer f.Close()
    h := sha256.New()
    _, _ = io.Copy(h, f)
    return hex.EncodeToString(h.Sum(nil))
}

func omissionDigest(e PartitionEntry) string {
    s := strings.Join([]string{e.PartitionID, e.OmissionReason, e.CursorStart, e.CursorEnd, e.PrevCursor}, "|")
    sum := sha256.Sum256([]byte(s))
    return hex.EncodeToString(sum[:])
}

func partitionSets(entries []PartitionEntry) ([]string, []string) {
    exported := []string{}
    omitted := []string{}
    for _, e := range entries {
        if e.Status == "export" { exported = append(exported, e.PartitionID) }
        if e.Status == "omit" { omitted = append(omitted, e.PartitionID) }
    }
    return exported, omitted
}

func collectMismatches(ws *Workspace) []string {
    var problems []string
    expByID := map[string]PartitionEntry{}
    for _, e := range ws.Expected { expByID[e.PartitionID] = e }
    manByID := map[string]PartitionEntry{}
    for _, e := range ws.Manifest.PartitionEntries { manByID[e.PartitionID] = e }
    ledByID := map[string]LedgerRow{}
    for _, r := range ws.Ledger { ledByID[r.PartitionID] = r }

    if ws.Manifest.SchemaVersion != 2 { problems = append(problems, "manifest schema_version must be 2") }
    if ws.State.SchemaVersion != 2 { problems = append(problems, "export_state schema_version must be 2") }
    if ws.State.Status != "complete" { problems = append(problems, "export_state status must be complete") }
    if !sameStrings(ws.State.Lineage, ws.Exported) { problems = append(problems, "export_state lineage does not match cursor trace exported partitions") }
    if !sameStrings(ws.State.OmittedPartitions, ws.Omitted) { problems = append(problems, "export_state omitted_partitions does not match cursor trace") }
    if len(ws.Expected) > 0 && ws.State.LastCompleteEventSeq != ws.Expected[len(ws.Expected)-1].Sequence { problems = append(problems, "export_state last_complete_event_seq is stale") }
    if len(ws.Exported) > 0 {
        last := ws.Exported[len(ws.Exported)-1]
        if ws.State.SucceededAfter != last { problems = append(problems, "export_state succeeded_after_partition is stale") }
        if ws.State.HighWaterCursor != expByID[last].CursorEnd { problems = append(problems, "export_state high_water_cursor is stale") }
    }
    expectedLineage := lineageHash(ws.Expected)
    if ws.Manifest.Signer.LineageHashHex != expectedLineage { problems = append(problems, "manifest signer.lineage_hash_hex does not match exported cursor lineage") }
    if ws.Manifest.Signer.KeyID == "" { problems = append(problems, "manifest signer.key_id is empty") }

    if len(ws.Manifest.PartitionEntries) != len(ws.Expected) { problems = append(problems, "manifest partition_entries count does not match cursor trace") }
    if len(ws.Ledger) != len(ws.Expected) { problems = append(problems, "ledger checkpoint row count does not match cursor trace") }
    for _, exp := range ws.Expected {
        man, ok := manByID[exp.PartitionID]
        if !ok { problems = append(problems, "manifest missing "+exp.PartitionID) } else if !entryEqual(man, exp) { problems = append(problems, "manifest entry mismatch for "+exp.PartitionID) }
        row, ok := ledByID[exp.PartitionID]
        if !ok { problems = append(problems, "ledger missing "+exp.PartitionID) } else if !ledgerEqual(row, exp) { problems = append(problems, "ledger row mismatch for "+exp.PartitionID) }
    }
    for _, row := range ws.Ledger {
        if row.Terminal != 1 { problems = append(problems, "ledger row not terminal for "+row.PartitionID) }
    }
    return unique(problems)
}

func entryEqual(a, b PartitionEntry) bool {
    return a.PartitionID == b.PartitionID && a.Sequence == b.Sequence && a.Path == b.Path && a.Status == b.Status && a.CursorStart == b.CursorStart && a.CursorEnd == b.CursorEnd && a.PrevCursor == b.PrevCursor && a.DigestHex == b.DigestHex && a.OmissionReason == b.OmissionReason && a.OmissionDigestHex == b.OmissionDigestHex
}

func ledgerEqual(r LedgerRow, e PartitionEntry) bool {
    return r.Sequence == e.Sequence && r.Status == e.Status && r.CursorStart == e.CursorStart && r.CursorEnd == e.CursorEnd && r.PrevCursor == e.PrevCursor && r.DigestHex == e.DigestHex && r.OmissionReason == e.OmissionReason && r.OmissionDigestHex == e.OmissionDigestHex
}

func sameStrings(a, b []string) bool {
    if len(a) != len(b) { return false }
    for i := range a { if a[i] != b[i] { return false } }
    return true
}

func lineageHash(entries []PartitionEntry) string {
    var b strings.Builder
    for _, e := range entries {
        if e.Status != "export" { continue }
        b.WriteString(e.PartitionID)
        b.WriteString("|")
        b.WriteString(e.PrevCursor)
        b.WriteString("|")
        b.WriteString(e.CursorEnd)
        b.WriteString("\n")
    }
    sum := sha256.Sum256([]byte(b.String()))
    return hex.EncodeToString(sum[:])
}

func unique(items []string) []string {
    seen := map[string]bool{}
    out := []string{}
    for _, item := range items {
        if !seen[item] { seen[item] = true; out = append(out, item) }
    }
    return out
}

func writeExport(ws *Workspace, out string) error {
    if err := os.MkdirAll(filepath.Join(out, "partitions"), 0o755); err != nil { return err }
    for _, e := range ws.Manifest.PartitionEntries {
        if e.Status != "export" { continue }
        src := filepath.Join(ws.Root, filepath.FromSlash(e.Path))
        dst := filepath.Join(out, "partitions", e.PartitionID+".journal")
        _ = copyFile(src, dst)
    }
    status := "complete"
    if len(ws.Mismatches) != 0 { status = "incomplete" }
    report := Report{
        SchemaVersion: 2,
        BundleID: ws.Manifest.BundleID,
        Status: status,
        ServiceUnit: ws.Manifest.ServiceUnit,
        HighWaterCursor: ws.State.HighWaterCursor,
        ExportedPartitions: ws.Exported,
        OmittedPartitions: ws.Omitted,
        LineageHashHex: lineageHash(ws.Expected),
        AuthorityMismatches: ws.Mismatches,
        Partitions: ws.Manifest.PartitionEntries,
    }
    manifestDigest := canonicalDigest(ws.Manifest.PartitionEntries)
    report.ManifestDigestHex = manifestDigest
    report.SignatureHex = signatureHex(ws.Manifest.Signer.KeyID, report.LineageHashHex, manifestDigest)
    if err := writePretty(filepath.Join(out, "compliance_report.json"), report); err != nil { return err }
    signed := map[string]any{
        "schema_version": ws.Manifest.SchemaVersion,
        "bundle_id": ws.Manifest.BundleID,
        "service_unit": ws.Manifest.ServiceUnit,
        "reload_generation": ws.Manifest.ReloadGeneration,
        "partition_entries": ws.Manifest.PartitionEntries,
        "signer": map[string]any{
            "key_id": ws.Manifest.Signer.KeyID,
            "signed_at": ws.Manifest.Signer.SignedAt,
            "lineage_hash_hex": ws.Manifest.Signer.LineageHashHex,
            "manifest_digest_hex": manifestDigest,
            "signature_hex": report.SignatureHex,
        },
    }
    return writePretty(filepath.Join(out, "bundle_manifest.signed.json"), signed)
}

func canonicalDigest(v any) string {
    raw, _ := json.Marshal(v)
    sum := sha256.Sum256(raw)
    return hex.EncodeToString(sum[:])
}

func signatureHex(key, lineage, manifest string) string {
    sum := sha256.Sum256([]byte(key+"\n"+lineage+"\n"+manifest))
    return hex.EncodeToString(sum[:])
}

func writePretty(path string, v any) error {
    raw, err := json.MarshalIndent(v, "", "  ")
    if err != nil { return err }
    raw = append(raw, '\n')
    return os.WriteFile(path, raw, 0o644)
}

func copyFile(src, dst string) error {
    in, err := os.Open(src)
    if err != nil { return err }
    defer in.Close()
    out, err := os.Create(dst)
    if err != nil { return err }
    defer out.Close()
    _, err = io.Copy(out, in)
    return err
}

func verifyLegacy(root string) error {
    raw, err := os.ReadFile(filepath.Join(root, "legacy", "bundle_manifest_v1.json"))
    if err != nil { return err }
    var payload struct { SchemaVersion int `json:"schema_version"`; PartitionEntries []PartitionEntry `json:"partition_entries"` }
    if err := json.Unmarshal(raw, &payload); err != nil { return err }
    if payload.SchemaVersion != 1 { return errors.New("legacy bundle must use schema_version 1") }
    prev := ""
    for i, e := range payload.PartitionEntries {
        if e.Status != "export" { return fmt.Errorf("legacy entry %s is not exported", e.PartitionID) }
        if i > 0 && e.PrevCursor != prev { return fmt.Errorf("legacy monotonic chain breaks at %s", e.PartitionID) }
        if got := sha256File(filepath.Join(root, filepath.FromSlash(e.Path))); got != e.DigestHex { return fmt.Errorf("legacy digest mismatch for %s", e.PartitionID) }
        if n, _ := strconv.Atoi(strings.TrimPrefix(strings.Split(e.CursorEnd, ";")[0], "s=")); n < 0 { return fmt.Errorf("legacy cursor parse failed for %s", e.PartitionID) }
        prev = e.CursorEnd
    }
    return nil
}
