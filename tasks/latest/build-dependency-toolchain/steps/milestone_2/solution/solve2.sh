#!/bin/bash
set -euo pipefail

export PATH="/usr/local/go/bin:/usr/bin:/bin:${PATH:-}"
export GOCACHE=/tmp/gocache

cd /app/repo
git switch main 2>/dev/null || git checkout main

cat > internal/routing/match.go << 'EOF'
package routing

func MatchRoute(pattern, path string) bool {
	return pattern == path
}
EOF

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

cat > internal/dispatch/queue.go << 'EOF'
package dispatch

func Dispatch(entries []string) []string {
	out := make([]string, len(entries))
	copy(out, entries)
	return out
}
EOF

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

git add internal/routing/match.go internal/ledger/ledger.go internal/dispatch/queue.go internal/deliver/attempt.go
git commit -m "Fix route matching, ledger persistence, dispatch order, and delivery idempotency"

go test ./... -count=1
test -z "$(git status --porcelain)"
