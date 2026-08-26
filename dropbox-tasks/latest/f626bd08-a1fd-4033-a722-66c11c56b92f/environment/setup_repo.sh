#!/bin/bash
set -euo pipefail

mkdir -p /app/repo
cd /app/repo
git init -b main
git config user.email "ops@relayd.io"
git config user.name "Relay Platform"

cat > .gitignore << 'EOF'
/relayd
*.test
EOF

cat > go.mod << 'EOF'
module github.com/acme/relayd

go 1.23
EOF

mkdir -p cmd/relayd internal/routing internal/ledger internal/dispatch internal/deliver

cat > cmd/relayd/main.go << 'EOF'
package main

func main() {}
EOF

git add .
git commit --date="2026-05-01T09:00:00" -m "Bootstrap relayd module"

# ------------------------------------------------------------------
# Commit 2: exact route matching
# ------------------------------------------------------------------
cat > internal/routing/match.go << 'EOF'
package routing

func MatchRoute(pattern, path string) bool {
	return pattern == path
}
EOF

cat > internal/routing/match_test.go << 'EOF'
package routing

import "testing"

func TestExactRouteMatch(t *testing.T) {
	if !MatchRoute("/hooks/billing", "/hooks/billing") {
		t.Fatal("exact route should match")
	}
	if MatchRoute("/hooks/billing", "/hooks/billing/extra") {
		t.Fatal("longer path should not match exact route")
	}
	if MatchRoute("/hooks/Billing", "/hooks/billing") {
		t.Fatal("routes must be case-sensitive")
	}
}
EOF

git add .
git commit --date="2026-05-02T10:15:00" -m "Add exact webhook route matching"

# ------------------------------------------------------------------
# Commit 3: durable delivery ledger
# ------------------------------------------------------------------
cat > internal/ledger/ledger.go << 'EOF'
package ledger

import (
	"bufio"
	"os"
	"strings"
)

type Ledger struct {
	path string
}

func NewLedger(path string) *Ledger {
	return &Ledger{path: path}
}

func (l *Ledger) Append(line string) error {
	f, err := os.OpenFile(l.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(line + "\n")
	return err
}

func (l *Ledger) LoadAll() ([]string, error) {
	data, err := os.ReadFile(l.path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	text := strings.TrimSpace(string(data))
	if text == "" {
		return nil, nil
	}
	var out []string
	scanner := bufio.NewScanner(strings.NewReader(text))
	for scanner.Scan() {
		out = append(out, scanner.Text())
	}
	return out, scanner.Err()
}
EOF

cat > internal/ledger/ledger_test.go << 'EOF'
package ledger

import (
	"path/filepath"
	"testing"
)

func TestLedgerSurvivesReload(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "deliveries.log")
	l1 := NewLedger(path)
	if err := l1.Append("delivery-1"); err != nil {
		t.Fatal(err)
	}
	l2 := NewLedger(path)
	entries, err := l2.LoadAll()
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 || entries[0] != "delivery-1" {
		t.Fatalf("expected persisted delivery-1, got %v", entries)
	}
}
EOF

git add .
git commit --date="2026-05-03T11:30:00" -m "Add append-only delivery ledger"

# ------------------------------------------------------------------
# Commit 4: submit-order dispatch queue
# ------------------------------------------------------------------
cat > internal/dispatch/queue.go << 'EOF'
package dispatch

func Dispatch(entries []string) []string {
	out := make([]string, len(entries))
	copy(out, entries)
	return out
}
EOF

cat > internal/dispatch/queue_test.go << 'EOF'
package dispatch

import (
	"strings"
	"testing"
)

func TestDispatchPreservesSubmitOrder(t *testing.T) {
	in := []string{"job-3", "job-1", "job-2"}
	out := Dispatch(in)
	if strings.Join(out, ",") != "job-3,job-1,job-2" {
		t.Fatalf("dispatch reordered entries: %v", out)
	}
}
EOF

git add .
git commit --date="2026-05-04T13:00:00" -m "Add submit-order dispatch queue"

# ------------------------------------------------------------------
# Commit 5: idempotent delivery attempts
# ------------------------------------------------------------------
cat > internal/deliver/attempt.go << 'EOF'
package deliver

import "github.com/acme/relayd/internal/ledger"

type Attemptor struct {
	ledger *ledger.Ledger
	seen   map[string]struct{}
}

func NewAttemptor(l *ledger.Ledger) *Attemptor {
	return &Attemptor{ledger: l, seen: make(map[string]struct{})}
}

func (a *Attemptor) Deliver(deliveryID, payload string) error {
	if _, ok := a.seen[deliveryID]; ok {
		return nil
	}
	a.seen[deliveryID] = struct{}{}
	return a.ledger.Append(payload)
}
EOF

cat > internal/deliver/attempt_test.go << 'EOF'
package deliver

import (
	"path/filepath"
	"testing"

	"github.com/acme/relayd/internal/ledger"
)

func TestDeliverIdempotent(t *testing.T) {
	dir := t.TempDir()
	l := ledger.NewLedger(filepath.Join(dir, "deliveries.log"))
	a := NewAttemptor(l)
	if err := a.Deliver("delivery-9", "payload-a"); err != nil {
		t.Fatal(err)
	}
	if err := a.Deliver("delivery-9", "payload-a"); err != nil {
		t.Fatal(err)
	}
	entries, err := l.LoadAll()
	if err != nil {
		t.Fatal(err)
	}
	if len(entries) != 1 {
		t.Fatalf("expected one ledger entry after retry, got %d", len(entries))
	}
}
EOF

git add .
git commit --date="2026-05-05T14:45:00" -m "Add idempotent delivery attempts"

# ------------------------------------------------------------------
# Commit 6: DECOY — rotate default retry cap constant
# ------------------------------------------------------------------
cat > internal/ledger/ledger.go << 'EOF'
package ledger

import (
	"bufio"
	"os"
	"strings"
)

const DefaultRetryCap = 5

type Ledger struct {
	path string
}

func NewLedger(path string) *Ledger {
	return &Ledger{path: path}
}

func (l *Ledger) Append(line string) error {
	f, err := os.OpenFile(l.path, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
	if err != nil {
		return err
	}
	defer f.Close()
	_, err = f.WriteString(line + "\n")
	return err
}

func (l *Ledger) LoadAll() ([]string, error) {
	data, err := os.ReadFile(l.path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	text := strings.TrimSpace(string(data))
	if text == "" {
		return nil, nil
	}
	var out []string
	scanner := bufio.NewScanner(strings.NewReader(text))
	for scanner.Scan() {
		out = append(out, scanner.Text())
	}
	return out, scanner.Err()
}
EOF

git add internal/ledger/ledger.go
git commit --date="2026-05-06T09:20:00" -m "Tune default retry cap"

# ------------------------------------------------------------------
# Commit 7: REGRESSION A — prefix routes
# ------------------------------------------------------------------
cat > internal/routing/match.go << 'EOF'
package routing

import "strings"

func MatchRoute(pattern, path string) bool {
	return strings.HasPrefix(path, pattern)
}
EOF

git add internal/routing/match.go
git commit --date="2026-05-07T16:05:00" -m "Match webhook routes by prefix"

# ------------------------------------------------------------------
# Commit 8: DECOY — startup log prefix
# ------------------------------------------------------------------
cat > cmd/relayd/main.go << 'EOF'
package main

import "log"

func main() {
	log.SetPrefix("[relayd] ")
}
EOF

git add cmd/relayd/main.go
git commit --date="2026-05-08T09:00:00" -m "Add startup log prefix"

# ------------------------------------------------------------------
# Commit 9: REGRESSION D — deliver ignores delivery ids
# ------------------------------------------------------------------
cat > internal/deliver/attempt.go << 'EOF'
package deliver

import "github.com/acme/relayd/internal/ledger"

type Attemptor struct {
	ledger *ledger.Ledger
}

func NewAttemptor(l *ledger.Ledger) *Attemptor {
	return &Attemptor{ledger: l}
}

func (a *Attemptor) Deliver(deliveryID, payload string) error {
	_ = deliveryID
	return a.ledger.Append(payload)
}
EOF

git add internal/deliver/attempt.go
git commit --date="2026-05-09T11:15:00" -m "Simplify delivery retry path"

# ------------------------------------------------------------------
# Commit 10: DECOY — ready log line
# ------------------------------------------------------------------
cat > cmd/relayd/main.go << 'EOF'
package main

import "log"

func main() {
	log.SetPrefix("[relayd] ")
	log.Println("ready")
}
EOF

git add cmd/relayd/main.go
git commit --date="2026-05-09T15:30:00" -m "Log ready state on startup"

# ------------------------------------------------------------------
# Commit 11: REGRESSION C — dispatch sorts jobs
# ------------------------------------------------------------------
cat > internal/dispatch/queue.go << 'EOF'
package dispatch

import "sort"

func Dispatch(entries []string) []string {
	out := append([]string(nil), entries...)
	sort.Strings(out)
	return out
}
EOF

git add internal/dispatch/queue.go
git commit --date="2026-05-10T10:20:00" -m "Canonicalize dispatch ordering"

# ------------------------------------------------------------------
# Commit 12: REGRESSION B — ledger append stays in memory
# ------------------------------------------------------------------
cat > internal/ledger/ledger.go << 'EOF'
package ledger

import (
	"bufio"
	"os"
	"strings"
)

const DefaultRetryCap = 5

type Ledger struct {
	path    string
	pending []string
}

func NewLedger(path string) *Ledger {
	return &Ledger{path: path}
}

func (l *Ledger) Append(line string) error {
	l.pending = append(l.pending, line)
	return nil
}

func (l *Ledger) LoadAll() ([]string, error) {
	data, err := os.ReadFile(l.path)
	if err != nil {
		if os.IsNotExist(err) {
			return nil, nil
		}
		return nil, err
	}
	text := strings.TrimSpace(string(data))
	if text == "" {
		return nil, nil
	}
	var out []string
	scanner := bufio.NewScanner(strings.NewReader(text))
	for scanner.Scan() {
		out = append(out, scanner.Text())
	}
	return out, scanner.Err()
}
EOF

git add internal/ledger/ledger.go
git commit --date="2026-05-11T13:55:00" -m "Buffer ledger appends before flush"

# ------------------------------------------------------------------
# Commit 13: DECOY — module comment only
# ------------------------------------------------------------------
cat > cmd/relayd/main.go << 'EOF'
// relayd forwards signed webhook deliveries through a durable ledger.
package main

import "log"

func main() {
	log.SetPrefix("[relayd] ")
	log.Println("ready")
}
EOF

git add cmd/relayd/main.go
git commit --date="2026-05-12T08:45:00" -m "Document relayd entrypoint"

# ------------------------------------------------------------------
# Commit 14: REGRESSION E — case-insensitive route matching
# ------------------------------------------------------------------
cat > internal/routing/match.go << 'EOF'
package routing

import "strings"

func MatchRoute(pattern, path string) bool {
	return strings.EqualFold(pattern, path)
}
EOF

git add internal/routing/match.go
git commit --date="2026-05-13T10:10:00" -m "Fold webhook route casing for client compatibility"

git checkout main
if [ -n "$(git status --porcelain)" ]; then
	echo "Warning: repository is not clean after setup"
fi
