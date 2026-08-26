#!/bin/bash
set -euo pipefail
cd /app
mkdir -p /app/internal/sp
cat > /app/internal/sp/sp.go <<'SPEOF'
package sp

import (
	"bytes"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"sort"
	"strconv"
)

// ---- canonical JSON (matches python json.dumps(sort_keys=True, indent=2)+"\n") ----
func Canonical(v any) ([]byte, error) {
	raw, err := json.Marshal(v)
	if err != nil {
		return nil, err
	}
	var generic any
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.UseNumber()
	if err := dec.Decode(&generic); err != nil {
		return nil, err
	}
	var buf bytes.Buffer
	enc := json.NewEncoder(&buf)
	enc.SetIndent("", "  ")
	enc.SetEscapeHTML(false)
	if err := enc.Encode(generic); err != nil {
		return nil, err
	}
	return buf.Bytes(), nil
}

func emit(v any) error {
	b, err := Canonical(v)
	if err != nil {
		return err
	}
	_, err = os.Stdout.Write(b)
	return err
}

// ---- value helpers (JSON semantics mirroring python) ----
func asStr(v any) (string, bool) {
	s, ok := v.(string)
	return s, ok
}

func asInt(v any) (int, bool) {
	n, ok := v.(json.Number)
	if !ok {
		return 0, false
	}
	i, err := strconv.ParseInt(n.String(), 10, 64)
	if err != nil {
		return 0, false
	}
	return int(i), true
}

func present(m map[string]any, k string) bool {
	v, ok := m[k]
	return ok && v != nil
}

// ---- input model ----
type Doc struct {
	Spool     string
	Printers  []string
	Budgets   map[string]int
	MaxFaults int
	Events    []map[string]any
}

func loadDoc(path string) (*Doc, error) {
	b, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	dec := json.NewDecoder(bytes.NewReader(b))
	dec.UseNumber()
	var top map[string]any
	if err := dec.Decode(&top); err != nil {
		return nil, err
	}
	d := &Doc{Budgets: map[string]int{}, MaxFaults: 3}
	if s, ok := asStr(top["spool"]); ok {
		d.Spool = s
	}
	if arr, ok := top["printers"].([]any); ok {
		for _, p := range arr {
			if s, ok := asStr(p); ok {
				d.Printers = append(d.Printers, s)
			}
		}
	}
	if bm, ok := top["budgets"].(map[string]any); ok {
		for k, v := range bm {
			if iv, ok := asInt(v); ok {
				d.Budgets[k] = iv
			}
		}
	}
	if mf, ok := asInt(top["max_faults"]); ok {
		d.MaxFaults = mf
	}
	if arr, ok := top["events"].([]any); ok {
		for _, e := range arr {
			if em, ok := e.(map[string]any); ok {
				d.Events = append(d.Events, em)
			}
		}
	}
	return d, nil
}

// ---- engine ----
type Job struct {
	ID       string
	Owner    string
	Printer  string
	Priority int
	Pages    int
	Seq      int
	State    string
	Faults   int
	Outcomes [][2]any
}

type Printer struct {
	ID      string
	Current string // "" means none
	HasCur  bool
	Paused  bool
}

type Preempt struct {
	AtSeq   int
	Printer string
	Victim  string
	By      string
}

type Engine struct {
	detect      bool
	sid         string
	porder      []string
	printers    map[string]*Printer
	budgets     map[string]int
	maxFaults   int
	jobs        map[string]*Job
	jorder      []string
	committed   map[string]int
	reserved    map[string]int
	committedPr map[[2]string]int
	log         []map[string]any
	preemptions []Preempt
	aborted     []string
}

func newEngine(d *Doc, detect bool) *Engine {
	e := &Engine{
		detect: detect, sid: d.Spool, maxFaults: d.MaxFaults,
		printers:    map[string]*Printer{},
		budgets:     map[string]int{},
		jobs:        map[string]*Job{},
		committed:   map[string]int{},
		reserved:    map[string]int{},
		committedPr: map[[2]string]int{},
	}
	for _, p := range d.Printers {
		e.porder = append(e.porder, p)
		e.printers[p] = &Printer{ID: p}
	}
	for k, v := range d.Budgets {
		e.budgets[k] = v
	}
	return e
}

func (e *Engine) hasBudget(owner string) bool {
	_, ok := e.budgets[owner]
	return ok
}

// remaining returns (value, unlimited)
func (e *Engine) remaining(owner string) (int, bool) {
	if !e.hasBudget(owner) {
		return 0, true
	}
	return e.budgets[owner] - e.committed[owner] - e.reserved[owner], false
}

func (e *Engine) affordable(owner string, pages int) bool {
	rem, unlimited := e.remaining(owner)
	return unlimited || rem >= pages
}

func (e *Engine) dispatch(pid string) {
	p := e.printers[pid]
	if p.Paused || p.HasCur {
		return
	}
	best := ""
	var bestPrio, bestFair, bestSeq int
	have := false
	for _, jid := range e.jorder {
		j := e.jobs[jid]
		if j.State != "queued" || j.Printer != pid {
			continue
		}
		if !e.affordable(j.Owner, j.Pages) {
			continue
		}
		prio := -j.Priority
		fair := e.committedPr[[2]string{pid, j.Owner}]
		seq := j.Seq
		if !have || prio < bestPrio ||
			(prio == bestPrio && fair < bestFair) ||
			(prio == bestPrio && fair == bestFair && seq < bestSeq) {
			best = jid
			bestPrio = prio
			bestFair = fair
			bestSeq = seq
			have = true
		}
	}
	if !have {
		return
	}
	j := e.jobs[best]
	j.State = "printing"
	p.Current = best
	p.HasCur = true
	e.reserved[j.Owner] += j.Pages
}

func (e *Engine) tryPreempt(jid string, seq int) {
	if !e.detect {
		return
	}
	j := e.jobs[jid]
	if j.State != "queued" {
		return
	}
	if !e.affordable(j.Owner, j.Pages) {
		return
	}
	p := e.printers[j.Printer]
	if p.Paused || !p.HasCur {
		return
	}
	k := e.jobs[p.Current]
	if j.Priority > k.Priority {
		e.reserved[k.Owner] -= k.Pages
		k.State = "queued"
		victim := k.ID
		pid := p.ID
		p.Current = ""
		p.HasCur = false
		e.preemptions = append(e.preemptions, Preempt{AtSeq: seq, Printer: pid, Victim: victim, By: jid})
		e.dispatch(pid)
	}
}

func (e *Engine) apply(ev map[string]any) {
	seq, _ := asInt(ev["seq"])
	op, _ := asStr(ev["op"])
	outcome, logJob, logPrinter := e.dispatchOp(ev, seq)
	e.log = append(e.log, map[string]any{
		"seq": seq, "op": op, "job": logJob, "printer": logPrinter, "outcome": outcome,
	})
	if s, ok := logJob.(string); ok {
		if j, ok := e.jobs[s]; ok {
			j.Outcomes = append(j.Outcomes, [2]any{seq, outcome})
		}
	}
}

func (e *Engine) dispatchOp(ev map[string]any, seq int) (string, any, any) {
	op, _ := asStr(ev["op"])
	switch op {
	case "submit":
		return e.opSubmit(ev, seq)
	case "finish":
		return e.opFinish(ev)
	case "hold":
		return e.opHold(ev)
	case "release":
		return e.opRelease(ev, seq)
	case "cancel":
		return e.opCancel(ev)
	case "pause":
		return e.opPause(ev)
	case "resume":
		return e.opResume(ev)
	case "fault":
		return e.opFault(ev)
	}
	return "rejected", nil, nil
}

func rawVal(ev map[string]any, k string) any {
	v, ok := ev[k]
	if !ok {
		return nil
	}
	return v
}

func (e *Engine) opSubmit(ev map[string]any, seq int) (string, any, any) {
	jobRaw := rawVal(ev, "job")
	printerRaw := rawVal(ev, "printer")
	jid, okJ := asStr(ev["job"])
	owner, okO := asStr(ev["owner"])
	printer, okP := asStr(ev["printer"])
	pages, okPg := asInt(ev["pages"])
	priority, okPr := asInt(ev["priority"])
	_, declared := e.printers[printer]
	_, dup := e.jobs[jid]
	bad := !okJ || !okO || !okP || !okPg || pages < 1 || !okPr || !declared || dup
	if bad {
		return "rejected", jobRaw, printerRaw
	}
	j := &Job{ID: jid, Owner: owner, Printer: printer, Priority: priority,
		Pages: pages, Seq: seq, State: "queued"}
	e.jobs[jid] = j
	e.jorder = append(e.jorder, jid)
	e.dispatch(printer)
	if j.State == "queued" {
		e.tryPreempt(jid, seq)
	}
	return j.State, jobRaw, printerRaw
}

func (e *Engine) opFinish(ev map[string]any) (string, any, any) {
	printerRaw := rawVal(ev, "printer")
	pid, ok := asStr(ev["printer"])
	p, exists := e.printers[pid]
	if !ok || !exists {
		return "rejected", nil, printerRaw
	}
	if !p.HasCur {
		return "noop", nil, printerRaw
	}
	j := e.jobs[p.Current]
	j.State = "done"
	e.committed[j.Owner] += j.Pages
	e.committedPr[[2]string{pid, j.Owner}] += j.Pages
	e.reserved[j.Owner] -= j.Pages
	p.Current = ""
	p.HasCur = false
	e.dispatch(pid)
	return "finished", nil, printerRaw
}

func (e *Engine) opHold(ev map[string]any) (string, any, any) {
	jobRaw := rawVal(ev, "job")
	jid, ok := asStr(ev["job"])
	j, exists := e.jobs[jid]
	if !ok || !exists {
		return "rejected", jobRaw, nil
	}
	if j.State == "queued" {
		j.State = "held"
		return "held", jobRaw, nil
	}
	if j.State == "held" {
		return "noop", jobRaw, nil
	}
	return "rejected", jobRaw, nil
}

func (e *Engine) opRelease(ev map[string]any, seq int) (string, any, any) {
	jobRaw := rawVal(ev, "job")
	jid, ok := asStr(ev["job"])
	j, exists := e.jobs[jid]
	if !ok || !exists {
		return "rejected", jobRaw, nil
	}
	if j.State == "held" {
		j.State = "queued"
		e.dispatch(j.Printer)
		if j.State == "queued" {
			e.tryPreempt(jid, seq)
		}
		return "released", jobRaw, nil
	}
	if j.State == "queued" {
		return "noop", jobRaw, nil
	}
	return "rejected", jobRaw, nil
}

func (e *Engine) opCancel(ev map[string]any) (string, any, any) {
	jobRaw := rawVal(ev, "job")
	jid, ok := asStr(ev["job"])
	j, exists := e.jobs[jid]
	if !ok || !exists {
		return "rejected", jobRaw, nil
	}
	if j.State == "done" || j.State == "canceled" || j.State == "aborted" {
		return "rejected", jobRaw, nil
	}
	if j.State == "queued" || j.State == "held" {
		j.State = "canceled"
		return "canceled", jobRaw, nil
	}
	// printing
	p := e.printers[j.Printer]
	p.Current = ""
	p.HasCur = false
	e.reserved[j.Owner] -= j.Pages
	j.State = "canceled"
	e.dispatch(j.Printer)
	return "canceled", jobRaw, nil
}

func (e *Engine) opPause(ev map[string]any) (string, any, any) {
	printerRaw := rawVal(ev, "printer")
	pid, ok := asStr(ev["printer"])
	p, exists := e.printers[pid]
	if !ok || !exists {
		return "rejected", nil, printerRaw
	}
	if !p.Paused {
		p.Paused = true
		return "paused", nil, printerRaw
	}
	return "noop", nil, printerRaw
}

func (e *Engine) opResume(ev map[string]any) (string, any, any) {
	printerRaw := rawVal(ev, "printer")
	pid, ok := asStr(ev["printer"])
	p, exists := e.printers[pid]
	if !ok || !exists {
		return "rejected", nil, printerRaw
	}
	if p.Paused {
		p.Paused = false
		e.dispatch(pid)
		return "resumed", nil, printerRaw
	}
	return "noop", nil, printerRaw
}

func (e *Engine) opFault(ev map[string]any) (string, any, any) {
	printerRaw := rawVal(ev, "printer")
	pid, ok := asStr(ev["printer"])
	p, exists := e.printers[pid]
	if !ok || !exists {
		return "rejected", nil, printerRaw
	}
	if !p.HasCur {
		return "noop", nil, printerRaw
	}
	j := e.jobs[p.Current]
	j.Faults++
	e.reserved[j.Owner] -= j.Pages
	p.Current = ""
	p.HasCur = false
	if j.Faults >= e.maxFaults {
		j.State = "aborted"
		e.aborted = append(e.aborted, j.ID)
		e.dispatch(pid)
		return "aborted", nil, printerRaw
	}
	j.State = "queued"
	e.dispatch(pid)
	return "faulted", nil, printerRaw
}

// ---- structural verify ----
var verifyPrec = map[string]int{"BAD_OP": 0, "MISSING_FIELD": 1, "BAD_PAGES": 2}
var knownOps = map[string]bool{"submit": true, "finish": true, "hold": true,
	"release": true, "cancel": true, "pause": true, "resume": true, "fault": true}

func verify(d *Doc) (int, string, bool) {
	haveBest := false
	bestSeq := 0
	bestReason := ""
	for _, ev := range d.Events {
		seq, _ := asInt(ev["seq"])
		op, _ := asStr(ev["op"])
		var reasons []string
		if !knownOps[op] {
			reasons = append(reasons, "BAD_OP")
		} else if op == "submit" {
			if !present(ev, "job") || !present(ev, "owner") || !present(ev, "printer") ||
				!present(ev, "pages") || !present(ev, "priority") {
				reasons = append(reasons, "MISSING_FIELD")
			}
			if present(ev, "pages") {
				pg, ok := asInt(ev["pages"])
				if !ok || pg < 1 {
					reasons = append(reasons, "BAD_PAGES")
				}
			}
		} else if op == "finish" || op == "pause" || op == "resume" || op == "fault" {
			if !present(ev, "printer") {
				reasons = append(reasons, "MISSING_FIELD")
			}
		} else if op == "hold" || op == "release" || op == "cancel" {
			if !present(ev, "job") {
				reasons = append(reasons, "MISSING_FIELD")
			}
		}
		if len(reasons) > 0 {
			best := reasons[0]
			for _, r := range reasons[1:] {
				if verifyPrec[r] < verifyPrec[best] {
					best = r
				}
			}
			if !haveBest || seq < bestSeq {
				haveBest = true
				bestSeq = seq
				bestReason = best
			}
		}
	}
	return bestSeq, bestReason, haveBest
}

func build(d *Doc, detect bool) *Engine {
	e := newEngine(d, detect)
	for _, ev := range d.Events {
		e.apply(ev)
	}
	return e
}

// ---- output builders ----
func (e *Engine) sortedPrinters() []string {
	out := append([]string{}, e.porder...)
	sort.Strings(out)
	return out
}

func (e *Engine) sortedJobs() []string {
	var out []string
	for id := range e.jobs {
		out = append(out, id)
	}
	sort.Strings(out)
	return out
}

func outLog(e *Engine) map[string]any {
	events := make([]any, len(e.log))
	for i, x := range e.log {
		events[i] = x
	}
	if events == nil {
		events = []any{}
	}
	return map[string]any{"spool": e.sid, "events": events}
}

func printerCurrent(p *Printer) any {
	if p.HasCur {
		return p.Current
	}
	return nil
}

func outPrinters(e *Engine) map[string]any {
	rows := []any{}
	for _, pid := range e.sortedPrinters() {
		p := e.printers[pid]
		rows = append(rows, map[string]any{
			"printer": pid, "current": printerCurrent(p), "paused": p.Paused})
	}
	return map[string]any{"spool": e.sid, "printers": rows}
}

func outQueues(e *Engine) map[string]any {
	rows := []any{}
	for _, pid := range e.sortedPrinters() {
		q := []any{}
		for _, jid := range e.jorder {
			j := e.jobs[jid]
			if j.Printer == pid && (j.State == "queued" || j.State == "held") {
				q = append(q, map[string]any{"job": j.ID, "owner": j.Owner,
					"priority": j.Priority, "pages": j.Pages, "state": j.State})
			}
		}
		if len(q) > 0 {
			rows = append(rows, map[string]any{"printer": pid, "queue": q})
		}
	}
	return map[string]any{"spool": e.sid, "printers": rows}
}

func outJobs(e *Engine) map[string]any {
	rows := []any{}
	for _, jid := range e.sortedJobs() {
		j := e.jobs[jid]
		rows = append(rows, map[string]any{"job": j.ID, "owner": j.Owner,
			"printer": j.Printer, "priority": j.Priority, "pages": j.Pages,
			"state": j.State})
	}
	return map[string]any{"spool": e.sid, "jobs": rows}
}

func outOwners(e *Engine) map[string]any {
	names := map[string]bool{}
	for o := range e.budgets {
		names[o] = true
	}
	for _, j := range e.jobs {
		names[j.Owner] = true
	}
	var ids []string
	for o := range names {
		ids = append(ids, o)
	}
	sort.Strings(ids)
	rows := []any{}
	for _, o := range ids {
		c := e.committed[o]
		r := e.reserved[o]
		var budget any
		var remaining any
		if e.hasBudget(o) {
			b := e.budgets[o]
			budget = b
			remaining = b - c - r
		}
		rows = append(rows, map[string]any{"owner": o, "budget": budget,
			"committed": c, "reserved": r, "remaining": remaining})
	}
	return map[string]any{"spool": e.sid, "owners": rows}
}

func outVerify(d *Doc) map[string]any {
	seq, reason, have := verify(d)
	var errObj any
	if have {
		errObj = map[string]any{"seq": seq, "reason": reason}
	}
	return map[string]any{"spool": d.Spool, "ok": !have, "error": errObj}
}

func outPreemptions(e *Engine) map[string]any {
	events := []any{}
	for _, d := range e.preemptions {
		events = append(events, map[string]any{"at_seq": d.AtSeq,
			"printer": d.Printer, "victim": d.Victim, "by": d.By})
	}
	return map[string]any{"spool": e.sid, "events": events, "count": len(e.preemptions)}
}

func outAborts(e *Engine) map[string]any {
	ab := []any{}
	for _, x := range e.aborted {
		ab = append(ab, x)
	}
	return map[string]any{"spool": e.sid, "aborted": ab, "count": len(e.aborted)}
}

func outJob(e *Engine, jid string) map[string]any {
	j, ok := e.jobs[jid]
	if !ok {
		return map[string]any{"spool": e.sid, "job": jid, "state": "unknown",
			"printer": nil, "owner": nil, "priority": nil, "pages": nil,
			"faults": 0, "outcomes": []any{}}
	}
	outs := []any{}
	for _, o := range j.Outcomes {
		outs = append(outs, map[string]any{"seq": o[0], "outcome": o[1]})
	}
	return map[string]any{"spool": e.sid, "job": j.ID, "state": j.State,
		"printer": j.Printer, "owner": j.Owner, "priority": j.Priority,
		"pages": j.Pages, "faults": j.Faults, "outcomes": outs}
}

func subDoc(d *Doc, n int) *Doc {
	if n < 0 {
		n = 0
	}
	if n > len(d.Events) {
		n = len(d.Events)
	}
	return &Doc{Spool: d.Spool, Printers: d.Printers, Budgets: d.Budgets,
		MaxFaults: d.MaxFaults, Events: d.Events[:n]}
}

// ---- dispatch (milestone 2: full model with preemption) ----
func Run(args []string) error {
	if len(args) == 0 {
		return errors.New("usage: spoold <command> ...")
	}
	cmd := args[0]
	if len(args) < 2 {
		return fmt.Errorf("usage: spoold %s <schedule>", cmd)
	}
	d, err := loadDoc(args[1])
	if err != nil {
		return err
	}
	if cmd == "verify" {
		return emit(outVerify(d))
	}
	if cmd == "trace" {
		if len(args) < 3 {
			return errors.New("usage: spoold trace <schedule> <n>")
		}
		n, err := strconv.Atoi(args[2])
		if err != nil {
			return err
		}
		e := build(subDoc(d, n), true)
		return emit(outPrinters(e))
	}
	if cmd == "job" {
		if len(args) < 3 {
			return errors.New("usage: spoold job <schedule> <job>")
		}
		e := build(d, true)
		return emit(outJob(e, args[2]))
	}
	e := build(d, true)
	switch cmd {
	case "log":
		return emit(outLog(e))
	case "printers":
		return emit(outPrinters(e))
	case "queues":
		return emit(outQueues(e))
	case "jobs":
		return emit(outJobs(e))
	case "owners":
		return emit(outOwners(e))
	case "preemptions":
		return emit(outPreemptions(e))
	case "aborts":
		return emit(outAborts(e))
	}
	return fmt.Errorf("unknown command: %s", cmd)
}

SPEOF
go build -o /app/bin/spoold ./cmd/spoold
