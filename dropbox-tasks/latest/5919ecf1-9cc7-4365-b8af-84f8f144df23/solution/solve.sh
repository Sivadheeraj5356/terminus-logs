#!/bin/bash
set -euo pipefail
APP_DIR="${APP_DIR:-/app}"
cat > "$APP_DIR/securities_lending_fee.go" <<'GO'
package main

import (
    "bufio"
    "encoding/csv"
    "encoding/json"
    "os"
    "path/filepath"
    "sort"
    "strconv"
    "strings"
    "time"
)

const cfgJSON = `{"num":87,"slug":"87-go-securities-lending-fee-ledger","title":"securities lending fee ledger","domain":"securities lending fee ledger","binary":"securities_lending_fee","src":"securities_lending_fee.go","out":"securities_lending_fee_report.json","manifest":"lending_batches.csv","entity":"borrowers.csv","events":"fee_accruals.jsonl","entity_name":"borrower_id","segment_name":"lending_desk","id_field":"fee_id","batch_field":"lending_batch_id","entity_field":"borrower_id","time_field":"accrued_at","seq_field":"loan_sequence","kind_field":"fee_type","amount_field":"fee_cents","ref_field":"rebates_fee_id","positive":"accrual","reverse":"rebate"}`

type Config struct { Manifest string `json:"manifest"`; Entity string `json:"entity"`; Events string `json:"events"`; Out string `json:"out"`; IdField string `json:"id_field"`; BatchField string `json:"batch_field"`; EntityField string `json:"entity_field"`; TimeField string `json:"time_field"`; SeqField string `json:"seq_field"`; KindField string `json:"kind_field"`; AmountField string `json:"amount_field"`; RefField string `json:"ref_field"`; Positive string `json:"positive"`; Reverse string `json:"reverse"` }
type Batch struct { ID string; Cutoff time.Time }
type Entity struct { ID, Segment string; Cap float64 }
type Event struct { ID, BatchID, EntityID, Kind, Ref string; Seq int; Amount float64; T time.Time; BadTime bool; Index int }
type Acc struct { ID, BatchID, EntityID string; Amount float64; Reversed bool }
type Curated struct { RecordID string `json:"record_id"`; EntityID string `json:"entity_id"`; Segment string `json:"segment"`; BatchID string `json:"batch_id"`; Amount float64 `json:"amount"` }
type EntSum struct { EntityID string `json:"entity_id"`; Segment string `json:"segment"`; CurrentRecords int `json:"current_records"`; ReversalCount int `json:"reversal_count"`; ActiveLimit float64 `json:"active_limit"`; NetAmount float64 `json:"net_amount"` }
type BatchAudit struct { BatchID string `json:"batch_id"`; AcceptedEvents int `json:"accepted_events"`; RejectedEvents int `json:"rejected_events"`; NetAmount float64 `json:"net_amount"` }
type EntityTrace struct { RecordID string `json:"record_id"`; BatchID string `json:"batch_id"`; EntityID string `json:"entity_id"`; CurrentRecords int `json:"current_records"`; ActiveAmount float64 `json:"active_amount"`; ReversalCount int `json:"reversal_count"` }
type Rej struct { RecordID string `json:"record_id"`; Reason string `json:"reason"` }
type Report struct { Curated []Curated `json:"curated_records"`; EntitySummary []EntSum `json:"entity_summary"`; BatchAudit []BatchAudit `json:"batch_audit"`; EntityTrace []EntityTrace `json:"entity_trace"`; Rejected []Rej `json:"rejected_records"`; Accepted []string `json:"accepted_records"` }

func trim(v interface{}) string {
    if s, ok := v.(string); ok { return strings.TrimSpace(s) }
    return ""
}

func num(v interface{}) float64 {
    switch x := v.(type) {
    case float64:
        return x
    case string:
        f, _ := strconv.ParseFloat(strings.TrimSpace(x), 64)
        return f
    default:
        return 0
    }
}

func main() {
    var c Config
    json.Unmarshal([]byte(cfgJSON), &c)
    in := os.Getenv("INPUT_DIR")
    if in == "" { in = "/app/input" }
    out := os.Getenv("OUTPUT_DIR")
    if out == "" { out = "/app/output" }

    batches := map[string]Batch{}
    bf, _ := os.Open(filepath.Join(in, c.Manifest))
    br, _ := csv.NewReader(bf).ReadAll()
    bf.Close()
    for _, r := range br[1:] {
        id := strings.TrimSpace(r[0])
        t, _ := time.Parse(time.RFC3339, strings.TrimSpace(r[1]))
        batches[id] = Batch{id, t.UTC()}
    }

    entities := map[string]Entity{}
    ef, _ := os.Open(filepath.Join(in, c.Entity))
    er, _ := csv.NewReader(ef).ReadAll()
    ef.Close()
    for _, r := range er[1:] {
        id := strings.TrimSpace(r[0])
        capAmount, _ := strconv.ParseFloat(strings.TrimSpace(r[2]), 64)
        entities[id] = Entity{id, strings.TrimSpace(r[1]), capAmount}
    }

    f, _ := os.Open(filepath.Join(in, c.Events))
    defer f.Close()
    events := []Event{}
    sc := bufio.NewScanner(f)
    idx := 0
    for sc.Scan() {
        var m map[string]interface{}
        json.Unmarshal(sc.Bytes(), &m)
        t, err := time.Parse(time.RFC3339, trim(m[c.TimeField]))
        events = append(events, Event{ID: trim(m[c.IdField]), BatchID: trim(m[c.BatchField]), EntityID: trim(m[c.EntityField]), Seq: int(num(m[c.SeqField])), Kind: trim(m[c.KindField]), Amount: num(m[c.AmountField]), Ref: trim(m[c.RefField]), T: t.UTC(), BadTime: err != nil, Index: idx})
        idx++
    }

    sort.SliceStable(events, func(i, j int) bool {
        a, b := events[i], events[j]
        if a.BadTime != b.BadTime { return a.BadTime }
        if a.BadTime { return a.Index < b.Index }
        if !a.T.Equal(b.T) { return a.T.Before(b.T) }
        if a.Seq != b.Seq { return a.Seq < b.Seq }
        return a.ID < b.ID
    })

    seen := map[string]bool{}
    accepted := map[string]*Acc{}
    acceptedOrder := []string{}
    rejected := []Rej{}
    entNet := map[string]float64{}
    entCurrent := map[string]int{}
    entRev := map[string]int{}
    batchNet := map[string]float64{}
    batchAcc := map[string]int{}
    batchRej := map[string]int{}
    trace := []EntityTrace{}

    for _, e := range events {
        reason := ""
        if e.BadTime {
            reason = "invalid timestamp"
        } else if seen[e.ID] {
            reason = "duplicate id"
        } else if _, ok := batches[e.BatchID]; !ok {
            reason = "unknown batch"
        } else if e.T.After(batches[e.BatchID].Cutoff) {
            reason = "after watermark"
        } else if _, ok := entities[e.EntityID]; !ok {
            reason = "unknown entity"
        } else if e.Kind != c.Positive && e.Kind != c.Reverse {
            reason = "invalid kind"
        } else if e.Kind == c.Positive && e.Amount < 0 {
            reason = "negative amount"
        } else if e.Kind == c.Positive && entNet[e.EntityID]+e.Amount > entities[e.EntityID].Cap {
            reason = "entity cap exceeded"
        }

        var rev *Acc
        if reason == "" && e.Kind == c.Reverse {
            prior, ok := accepted[e.Ref]
            if !ok || prior.Reversed || prior.EntityID != e.EntityID {
                reason = "state conflict"
            } else {
                rev = prior
            }
        }

        seen[e.ID] = true
        if reason != "" {
            rejected = append(rejected, Rej{e.ID, reason})
            if _, ok := batches[e.BatchID]; ok { batchRej[e.BatchID]++ }
            continue
        }

        acceptedOrder = append(acceptedOrder, e.ID)
        batchAcc[e.BatchID]++
        if e.Kind == c.Positive {
            accepted[e.ID] = &Acc{e.ID, e.BatchID, e.EntityID, e.Amount, false}
            entNet[e.EntityID] += e.Amount
            entCurrent[e.EntityID]++
            batchNet[e.BatchID] += e.Amount
        } else {
            rev.Reversed = true
            entNet[e.EntityID] -= rev.Amount
            entCurrent[e.EntityID]--
            entRev[e.EntityID]++
            batchNet[e.BatchID] -= rev.Amount
        }
        trace = append(trace, EntityTrace{e.ID, e.BatchID, e.EntityID, entCurrent[e.EntityID], entNet[e.EntityID], entRev[e.EntityID]})
    }

    curated := []Curated{}
    for _, a := range accepted {
        if !a.Reversed {
            en := entities[a.EntityID]
            curated = append(curated, Curated{a.ID, a.EntityID, en.Segment, a.BatchID, a.Amount})
        }
    }
    sort.Slice(curated, func(i, j int) bool { return curated[i].RecordID < curated[j].RecordID })

    eids := []string{}
    for id := range entities { eids = append(eids, id) }
    sort.Strings(eids)
    summaries := []EntSum{}
    for _, id := range eids {
        en := entities[id]
        summaries = append(summaries, EntSum{id, en.Segment, entCurrent[id], entRev[id], en.Cap, entNet[id]})
    }

    bids := []string{}
    for id := range batches { bids = append(bids, id) }
    sort.Strings(bids)
    audits := []BatchAudit{}
    for _, id := range bids {
        audits = append(audits, BatchAudit{id, batchAcc[id], batchRej[id], batchNet[id]})
    }
    sort.SliceStable(rejected, func(i, j int) bool { return rejected[i].RecordID < rejected[j].RecordID })

    os.MkdirAll(out, 0755)
    of, _ := os.Create(filepath.Join(out, c.Out))
    defer of.Close()
    enc := json.NewEncoder(of)
    enc.SetIndent("", "  ")
    enc.Encode(Report{curated, summaries, audits, trace, rejected, acceptedOrder})
}
GO
gofmt -w "$APP_DIR/securities_lending_fee.go"
go build -o "$APP_DIR/securities_lending_fee" "$APP_DIR/securities_lending_fee.go"
INPUT_DIR="${INPUT_DIR:-$APP_DIR/input}" OUTPUT_DIR="${OUTPUT_DIR:-$APP_DIR/output}" "$APP_DIR/securities_lending_fee"
