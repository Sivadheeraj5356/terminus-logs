#!/usr/bin/env bash
set -euo pipefail

export PATH="/opt/venv/bin:/usr/local/go/bin:/usr/local/cargo/bin:${PATH}"

APP_DIR="${TASK_ENV:-/app/environment}"

python3 - <<'SOLVE_ROUTE_TABLE_PY'
from pathlib import Path
import os

app = Path(os.environ.get("TASK_ENV", "/app/environment"))
roles = ['ops', 'finance', 'carrier', 'support', 'admin', 'auditor', 'partner', 'worker']
scopes = ['north', 'south', 'east', 'west', 'global', 'retail', 'wholesale', 'intl', 'archive', 'priority', 'standard', 'field', 'warehouse', 'cold', 'fragile', 'bulk']
states = ['draft', 'queued', 'active', 'settled', 'paused', 'closing', 'replay', 'audit']
lang = "go"

def actor(i): return roles[i % len(roles)]
def scope(i): return scopes[(i * 3 + 1) % len(scopes)]
def phase(i): return states[(i * 5 + 2) % len(states)]
def limit(i): return 80 + (i % 9) * 15

def mode(i):
    if 48 <= i <= 55 or 64 <= i <= 71: return "SCOPE_FLEX"
    if 56 <= i <= 63 or 72 <= i <= 79: return "STATE_FLEX"
    return "STRICT"

def c_route(i):
    return f"""#include "route_{i:03d}.h"

Rule route_{i:03d}_rule(void) {{
    Rule r = {{"{actor(i)}", "{scope(i)}", "{phase(i)}", {limit(i)}, "{mode(i)}"}};
    return r;
}}
"""

def cpp_route(i):
    return f"""#include "route_{i:03d}.hpp"

Rule route_{i:03d}_rule() {{
    return Rule{{"{actor(i)}", "{scope(i)}", "{phase(i)}", {limit(i)}, "{mode(i)}"}};
}}
"""

def go_route(i):
    return f"""package main

func route{i:03d}() Rule {{
    return Rule{{Actor: "{actor(i)}", Scope: "{scope(i)}", Phase: "{phase(i)}", Limit: {limit(i)}, Mode: "{mode(i)}"}}
}}
"""

def rust_route(i):
    return f"""use crate::types::Rule;

pub fn rule() -> Rule {{
    Rule {{ actor: "{actor(i)}", scope: "{scope(i)}", phase: "{phase(i)}", limit: {limit(i)}, mode: "{mode(i)}" }}
}}
"""

(app / "parser.go").write_text("""package main

import (
    "strconv"
    "strings"
)

func parseRequest(line string) (Request, bool) {
    fields := strings.Fields(line)
    if len(fields) != 8 || fields[0] != "REQ" {
        return Request{}, false
    }
    routeID, err := strconv.Atoi(fields[2])
    if err != nil || routeID < 0 || routeID > 127 {
        return Request{}, false
    }
    units, err := strconv.Atoi(fields[6])
    if err != nil || units < 0 {
        return Request{}, false
    }
    segment, err := strconv.Atoi(fields[7])
    if err != nil || (segment != 0 && segment != 1) {
        return Request{}, false
    }
    return Request{ID: fields[1], RouteID: routeID, Actor: fields[3], Scope: fields[4], Phase: fields[5], Units: units, Segment: segment}, true
}
""", encoding="utf-8")

(app / "policy.go").write_text("""package main

func evaluate(rule Rule, req Request) bool {
    if rule.Mode == "" {
        return false
    }
    if req.Units < 0 || (req.Segment != 0 && req.Segment != 1) {
        return false
    }
    if rule.Mode != "STATE_FLEX" && req.Segment != 0 {
        return false
    }
    capacity := rule.Limit
    if rule.Mode == "STATE_FLEX" && req.Segment == 1 {
        capacity *= 2
    }
    if req.Units > capacity {
        return false
    }
    if rule.Mode == "OPEN" {
        return true
    }
    if req.Actor != rule.Actor {
        return false
    }
    if rule.Mode == "SCOPE_FLEX" {
        return req.Scope == rule.Scope
    }
    if rule.Mode == "STATE_FLEX" {
        return req.Phase == rule.Phase
    }
    return req.Scope == rule.Scope && req.Phase == rule.Phase
}
""", encoding="utf-8")

(app / "main.go").write_text("""package main

import (
    "bufio"
    "fmt"
    "io"
    "os"
    "strconv"
    "strings"
)

type checkpoint struct {
    Actor   string
    Scope   string
    Phase   string
    Units   int
    Segment int
    Ttl     int
}

type overlay struct {
    LeftRouteID  int
    RightRouteID int
    Paired       bool
    Ttl          int
}

type budget struct {
    Remaining int
    Ttl       int
}

type lease struct {
    Actor    string
    MaxUnits int
    Ttl      int
}

type rate struct {
    Remaining int
    Ttl       int
}

type replayDecision struct {
    Decision string
    RouteID  int
}

type batchState struct {
    Mode      string
    SortBlock int
    Next      int
}

func parsePin(line string) (int, checkpoint, bool) {
    fields := strings.Fields(line)
    if len(fields) != 7 || fields[0] != "PIN" {
        return 0, checkpoint{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, checkpoint{}, false
    }
    units, err := strconv.Atoi(fields[5])
    if err != nil || units < 0 {
        return 0, checkpoint{}, false
    }
    segment, err := strconv.Atoi(fields[6])
    if err != nil || (segment != 0 && segment != 1) {
        return 0, checkpoint{}, false
    }
    return routeID, checkpoint{
        Actor:   fields[2],
        Scope:   fields[3],
        Phase:   fields[4],
        Units:   units,
        Segment: segment,
        Ttl:     -1,
    }, true
}

func parseHold(line string) (int, checkpoint, bool) {
    fields := strings.Fields(line)
    if len(fields) != 8 || fields[0] != "HOLD" {
        return 0, checkpoint{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, checkpoint{}, false
    }
    ttl, err := strconv.Atoi(fields[2])
    if err != nil || ttl <= 0 {
        return 0, checkpoint{}, false
    }
    units, err := strconv.Atoi(fields[6])
    if err != nil || units < 0 {
        return 0, checkpoint{}, false
    }
    segment, err := strconv.Atoi(fields[7])
    if err != nil || (segment != 0 && segment != 1) {
        return 0, checkpoint{}, false
    }
    return routeID, checkpoint{
        Actor:   fields[3],
        Scope:   fields[4],
        Phase:   fields[5],
        Units:   units,
        Segment: segment,
        Ttl:     ttl,
    }, true
}

func parseMap(line string) (int, overlay, bool) {
    fields := strings.Fields(line)
    if len(fields) != 4 || fields[0] != "MAP" {
        return 0, overlay{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, overlay{}, false
    }
    sourceRouteID, err := strconv.Atoi(fields[2])
    if err != nil || sourceRouteID < 0 || sourceRouteID > 127 {
        return 0, overlay{}, false
    }
    ttl, err := strconv.Atoi(fields[3])
    if err != nil || ttl <= 0 {
        return 0, overlay{}, false
    }
    return routeID, overlay{LeftRouteID: sourceRouteID, Ttl: ttl}, true
}

func parsePair(line string) (int, overlay, bool) {
    fields := strings.Fields(line)
    if len(fields) != 5 || fields[0] != "PAIR" {
        return 0, overlay{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, overlay{}, false
    }
    leftRouteID, err := strconv.Atoi(fields[2])
    if err != nil || leftRouteID < 0 || leftRouteID > 127 {
        return 0, overlay{}, false
    }
    rightRouteID, err := strconv.Atoi(fields[3])
    if err != nil || rightRouteID < 0 || rightRouteID > 127 {
        return 0, overlay{}, false
    }
    ttl, err := strconv.Atoi(fields[4])
    if err != nil || ttl <= 0 {
        return 0, overlay{}, false
    }
    return routeID, overlay{
        LeftRouteID:  leftRouteID,
        RightRouteID: rightRouteID,
        Paired:       true,
        Ttl:          ttl,
    }, true
}

func parseBudget(line string) (int, budget, bool) {
    fields := strings.Fields(line)
    if len(fields) != 4 || fields[0] != "BUDGET" {
        return 0, budget{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, budget{}, false
    }
    ttl, err := strconv.Atoi(fields[2])
    if err != nil || ttl <= 0 {
        return 0, budget{}, false
    }
    maxUnits, err := strconv.Atoi(fields[3])
    if err != nil || maxUnits < 0 {
        return 0, budget{}, false
    }
    return routeID, budget{Remaining: maxUnits, Ttl: ttl}, true
}

func parseSeal(line string) (int, checkpoint, bool) {
    fields := strings.Fields(line)
    if len(fields) != 8 || fields[0] != "SEAL" {
        return 0, checkpoint{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, checkpoint{}, false
    }
    ttl, err := strconv.Atoi(fields[2])
    if err != nil || ttl <= 0 {
        return 0, checkpoint{}, false
    }
    units, err := strconv.Atoi(fields[6])
    if err != nil || units < 0 {
        return 0, checkpoint{}, false
    }
    segment, err := strconv.Atoi(fields[7])
    if err != nil || (segment != 0 && segment != 1) {
        return 0, checkpoint{}, false
    }
    return routeID, checkpoint{
        Actor:   fields[3],
        Scope:   fields[4],
        Phase:   fields[5],
        Units:   units,
        Segment: segment,
        Ttl:     ttl,
    }, true
}

func parseLease(line string) (int, lease, bool) {
    fields := strings.Fields(line)
    if len(fields) != 5 || fields[0] != "LEASE" {
        return 0, lease{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, lease{}, false
    }
    ttl, err := strconv.Atoi(fields[2])
    if err != nil || ttl <= 0 {
        return 0, lease{}, false
    }
    if fields[3] == "" {
        return 0, lease{}, false
    }
    maxUnits, err := strconv.Atoi(fields[4])
    if err != nil || maxUnits < 0 {
        return 0, lease{}, false
    }
    return routeID, lease{Actor: fields[3], MaxUnits: maxUnits, Ttl: ttl}, true
}

func parseRate(line string) (int, rate, bool) {
    fields := strings.Fields(line)
    if len(fields) != 4 || fields[0] != "RATE" {
        return 0, rate{}, false
    }
    routeID, err := strconv.Atoi(fields[1])
    if err != nil || routeID < 0 || routeID > 127 {
        return 0, rate{}, false
    }
    ttl, err := strconv.Atoi(fields[2])
    if err != nil || ttl <= 0 {
        return 0, rate{}, false
    }
    maxAllows, err := strconv.Atoi(fields[3])
    if err != nil || maxAllows < 0 {
        return 0, rate{}, false
    }
    return routeID, rate{Remaining: maxAllows, Ttl: ttl}, true
}

func matchesCheckpoint(req Request, pin checkpoint) bool {
    return req.Actor == pin.Actor &&
        req.Scope == pin.Scope &&
        req.Phase == pin.Phase &&
        req.Units == pin.Units &&
        req.Segment == pin.Segment
}

func ageHolds(checkpoints map[int]checkpoint, activeRoute int) {
    for routeID, pin := range checkpoints {
        if routeID == activeRoute || pin.Ttl < 0 {
            continue
        }
        pin.Ttl--
        if pin.Ttl <= 0 {
            delete(checkpoints, routeID)
            continue
        }
        checkpoints[routeID] = pin
    }
}

func ageOverlay(overlays map[int]overlay, activeRoute int) {
    entry, found := overlays[activeRoute]
    if !found {
        return
    }
    entry.Ttl--
    if entry.Ttl <= 0 {
        delete(overlays, activeRoute)
        return
    }
    overlays[activeRoute] = entry
}

func ageBudget(budgets map[int]budget, activeRoute int) {
    entry, found := budgets[activeRoute]
    if !found {
        return
    }
    entry.Ttl--
    if entry.Ttl <= 0 {
        delete(budgets, activeRoute)
        return
    }
    budgets[activeRoute] = entry
}

func ageLease(leases map[int]lease, activeRoute int) {
    entry, found := leases[activeRoute]
    if !found {
        return
    }
    entry.Ttl--
    if entry.Ttl <= 0 {
        delete(leases, activeRoute)
        return
    }
    leases[activeRoute] = entry
}

func ageRate(rates map[int]rate, activeRoute int) {
    entry, found := rates[activeRoute]
    if !found {
        return
    }
    entry.Ttl--
    if entry.Ttl <= 0 {
        delete(rates, activeRoute)
        return
    }
    rates[activeRoute] = entry
}

func ageSeal(seals map[int]checkpoint, activeRoute int) {
    entry, found := seals[activeRoute]
    if !found {
        return
    }
    entry.Ttl--
    if entry.Ttl <= 0 {
        delete(seals, activeRoute)
        return
    }
    seals[activeRoute] = entry
}

func copySeen(seen map[int]bool) map[int]bool {
    out := map[int]bool{}
    for routeID, value := range seen {
        out[routeID] = value
    }
    return out
}

func evaluateResolved(routeID int, req Request, overlays map[int]overlay, seen map[int]bool) bool {
    if seen[routeID] {
        return false
    }
    seen[routeID] = true
    if entry, found := overlays[routeID]; found {
        if entry.Paired {
            return evaluateResolved(entry.LeftRouteID, req, overlays, copySeen(seen)) &&
                evaluateResolved(entry.RightRouteID, req, overlays, copySeen(seen))
        }
        return evaluateResolved(entry.LeftRouteID, req, overlays, seen)
    }
    rule, ok := getRouteRule(routeID)
    return ok && evaluate(rule, req)
}

func parseSequenceMarker(requestID string) (string, int, bool) {
    if strings.Count(requestID, ":") != 1 {
        return "", 0, false
    }
    parts := strings.SplitN(requestID, ":", 2)
    if parts[0] == "" || parts[1] == "" {
        return "", 0, false
    }
    for _, ch := range parts[1] {
        if ch < '0' || ch > '9' {
            return "", 0, false
        }
    }
    seq, err := strconv.Atoi(parts[1])
    if err != nil || seq < 1 || seq > 4096 {
        return "", 0, false
    }
    return parts[0], seq, true
}

func isUnsequencedReplayKey(requestID string) bool {
    _, _, marked := parseSequenceMarker(requestID)
    return !marked
}

func checkBatchState(req Request, batches map[string]batchState, prefixOwners map[string]string) (bool, func()) {
    prefix, seq, marked := parseSequenceMarker(req.ID)
    if !marked {
        return true, func() {}
    }
    if owner, found := prefixOwners[prefix]; found && owner != req.Actor {
        return false, func() {}
    }
    rule, ok := getRouteRule(req.RouteID)
    if !ok {
        return false, func() {}
    }
    sortBlock := req.RouteID / 16
    key := prefix + "\\x00" + req.Actor
    current, found := batches[key]
    if !found {
        if seq != 1 {
            return false, func() {}
        }
        prefixOwners[prefix] = req.Actor
        batches[key] = batchState{Mode: rule.Mode, SortBlock: sortBlock, Next: 2}
        return true, func() {
            delete(prefixOwners, prefix)
            delete(batches, key)
        }
    }
    if seq != current.Next {
        return false, func() {}
    }
    previous := current
    current.Next++
    batches[key] = current
    if current.Mode != rule.Mode || current.SortBlock != sortBlock {
        return false, func() {}
    }
    return true, func() {
        batches[key] = previous
    }
}

func main() {
    var input io.Reader = os.Stdin
    if len(os.Args) > 1 {
        file, err := os.Open(os.Args[1])
        if err != nil {
            os.Exit(2)
        }
        defer file.Close()
        input = file
    }

    scanner := bufio.NewScanner(input)
    checkpoints := map[int]checkpoint{}
    overlays := map[int]overlay{}
    seals := map[int]checkpoint{}
    budgets := map[int]budget{}
    leases := map[int]lease{}
    rates := map[int]rate{}
    batches := map[string]batchState{}
    prefixOwners := map[string]string{}
    replays := map[string]replayDecision{}
    for scanner.Scan() {
        line := scanner.Text()
        if strings.TrimSpace(line) == "" || strings.HasPrefix(line, "#") {
            continue
        }
        if req, ok := parseRequest(line); ok {
            replayKey := isUnsequencedReplayKey(req.ID)
            if replayKey {
                if replay, found := replays[req.ID]; found {
                    fmt.Printf("%s %s %d\\n", req.ID, replay.Decision, replay.RouteID)
                    continue
                }
            }
            if pin, found := checkpoints[req.RouteID]; found {
                delete(checkpoints, req.RouteID)
                if !matchesCheckpoint(req, pin) {
                    if replayKey {
                        replays[req.ID] = replayDecision{Decision: "DENY", RouteID: req.RouteID}
                    }
                    fmt.Printf("%s DENY %d\\n", req.ID, req.RouteID)
                    ageHolds(checkpoints, req.RouteID)
                    ageOverlay(overlays, req.RouteID)
                    ageBudget(budgets, req.RouteID)
                    ageSeal(seals, req.RouteID)
                    ageLease(leases, req.RouteID)
                    ageRate(rates, req.RouteID)
                    continue
                }
            }
            if entry, found := leases[req.RouteID]; found {
                if req.Actor != entry.Actor || req.Units > entry.MaxUnits {
                    if replayKey {
                        replays[req.ID] = replayDecision{Decision: "DENY", RouteID: req.RouteID}
                    }
                    fmt.Printf("%s DENY %d\\n", req.ID, req.RouteID)
                    ageHolds(checkpoints, req.RouteID)
                    ageOverlay(overlays, req.RouteID)
                    ageBudget(budgets, req.RouteID)
                    ageSeal(seals, req.RouteID)
                    ageLease(leases, req.RouteID)
                    ageRate(rates, req.RouteID)
                    continue
                }
            }
            if entry, found := seals[req.RouteID]; found {
                if !matchesCheckpoint(req, entry) {
                    if replayKey {
                        replays[req.ID] = replayDecision{Decision: "DENY", RouteID: req.RouteID}
                    }
                    fmt.Printf("%s DENY %d\\n", req.ID, req.RouteID)
                    ageHolds(checkpoints, req.RouteID)
                    ageOverlay(overlays, req.RouteID)
                    ageBudget(budgets, req.RouteID)
                    ageSeal(seals, req.RouteID)
                    ageLease(leases, req.RouteID)
                    ageRate(rates, req.RouteID)
                    continue
                }
            }
            sequenceOK, rollbackSequence := checkBatchState(req, batches, prefixOwners)
            if !sequenceOK {
                if replayKey {
                    replays[req.ID] = replayDecision{Decision: "DENY", RouteID: req.RouteID}
                }
                fmt.Printf("%s DENY %d\\n", req.ID, req.RouteID)
                ageHolds(checkpoints, req.RouteID)
                ageOverlay(overlays, req.RouteID)
                ageBudget(budgets, req.RouteID)
                ageSeal(seals, req.RouteID)
                ageLease(leases, req.RouteID)
                ageRate(rates, req.RouteID)
                continue
            }
            decision := "DENY"
            if evaluateResolved(req.RouteID, req, overlays, map[int]bool{}) {
                decision = "ALLOW"
            }
            if decision == "ALLOW" {
                if entry, found := rates[req.RouteID]; found {
                    if entry.Remaining <= 0 {
                        decision = "DENY"
                    } else {
                        entry.Remaining--
                        rates[req.RouteID] = entry
                    }
                }
            }
            if decision == "ALLOW" {
                if entry, found := budgets[req.RouteID]; found {
                    if req.Units > entry.Remaining {
                        decision = "DENY"
                    } else {
                        entry.Remaining -= req.Units
                        budgets[req.RouteID] = entry
                    }
                }
            }
            if decision == "DENY" {
                rollbackSequence()
            }
            if replayKey {
                replays[req.ID] = replayDecision{Decision: decision, RouteID: req.RouteID}
            }
            fmt.Printf("%s %s %d\\n", req.ID, decision, req.RouteID)
            ageHolds(checkpoints, req.RouteID)
            ageOverlay(overlays, req.RouteID)
            ageBudget(budgets, req.RouteID)
            ageSeal(seals, req.RouteID)
            ageLease(leases, req.RouteID)
            ageRate(rates, req.RouteID)
            continue
        }
        if routeID, pin, ok := parsePin(line); ok {
            checkpoints[routeID] = pin
            continue
        }
        if routeID, pin, ok := parseHold(line); ok {
            checkpoints[routeID] = pin
            continue
        }
        if routeID, entry, ok := parseMap(line); ok {
            overlays[routeID] = entry
            continue
        }
        if routeID, entry, ok := parsePair(line); ok {
            overlays[routeID] = entry
            continue
        }
        if routeID, entry, ok := parseBudget(line); ok {
            budgets[routeID] = entry
            continue
        }
        if routeID, entry, ok := parseSeal(line); ok {
            seals[routeID] = entry
            continue
        }
        if routeID, entry, ok := parseLease(line); ok {
            leases[routeID] = entry
            continue
        }
        if routeID, entry, ok := parseRate(line); ok {
            rates[routeID] = entry
        }
    }
}
""", encoding="utf-8")

for i in range(128):
    if 64 <= i <= 79:
        continue
    if lang == "c":
        path = app / "src" / f"route_{i:03d}.c"
        expected = c_route(i)
    elif lang == "cpp":
        path = app / "src" / f"route_{i:03d}.cpp"
        expected = cpp_route(i)
    elif lang == "go":
        path = app / f"route_{i:03d}.go"
        expected = go_route(i)
    elif lang == "rust":
        path = app / "src" / "routes" / f"route_{i:03d}.rs"
        expected = rust_route(i)
    else:
        raise SystemExit(f"unsupported language {lang}")
    if path.read_text(encoding="utf-8") != expected:
        path.write_text(expected, encoding="utf-8")
SOLVE_ROUTE_TABLE_PY

make -C "$APP_DIR" clean
make -C "$APP_DIR" test
