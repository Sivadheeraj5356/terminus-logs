#!/bin/bash
set -eu

export PATH="/usr/local/go/bin:/usr/bin:/bin:${PATH:-}"
export GOCACHE=/tmp/gocache

mkdir -p /app/reports
cd /app/repo
git switch main 2>/dev/null || git checkout main

cat > /tmp/bisect_gate.sh << 'GATE'
#!/bin/bash
set -eu
export PATH="/usr/local/go/bin:/usr/bin:/bin:${PATH:-}"
export GOCACHE=/tmp/gocache
NAME="$1"
cd /app/repo
for pkg in internal/routing internal/ledger internal/dispatch internal/deliver; do
  listing=$(git ls-tree --name-only "HEAD:${pkg}" 2>/dev/null || true)
  for f in $listing; do
    case "$f" in
      *_test.go)
        if git show "HEAD:${pkg}/${f}" 2>/dev/null | grep -q "func ${NAME}"; then
          go test "./${pkg}" -run "^${NAME}$" -count=1
          exit $?
        fi
        ;;
    esac
  done
done
exit 125
GATE
chmod +x /tmp/bisect_gate.sh

FAILING=$(go test ./... -count=1 2>&1 | awk '/^--- FAIL:/ {print $3}' | sort -u)

: > /app/reports/regression_commits.txt

for NAME in $FAILING; do
  git bisect start >/dev/null
  git bisect bad HEAD >/dev/null
  FIRST_WITH_TEST=$(
    git log --reverse -S "func ${NAME}" --format="%H" -- internal/routing internal/ledger internal/dispatch internal/deliver | head -n 1
  )
  git bisect good "$FIRST_WITH_TEST" >/dev/null
  BISECT_OUT=$(git bisect run /tmp/bisect_gate.sh "$NAME" 2>&1 || true)
  SHA=$(printf '%s\n' "$BISECT_OUT" | grep "first bad commit" | grep -oE "[0-9a-f]{40}" | head -n 1)
  if [ -z "$SHA" ]; then
    echo "bisect failed for ${NAME}" >&2
    printf '%s\n' "$BISECT_OUT" >&2
    exit 1
  fi
  echo "$SHA" >> /app/reports/regression_commits.txt
  git bisect reset >/dev/null
done

sort -u /app/reports/regression_commits.txt -o /app/reports/regression_commits.txt
git switch main 2>/dev/null || git checkout main
