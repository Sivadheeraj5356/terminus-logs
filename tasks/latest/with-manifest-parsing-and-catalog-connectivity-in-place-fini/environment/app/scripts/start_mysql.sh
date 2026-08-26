#!/bin/bash
set -euo pipefail

if mysqladmin ping -h127.0.0.1 --silent 2>/dev/null; then
  exit 0
fi

install -d -o mysql -g mysql /var/run/mysqld
mariadbd --user=mysql --bind-address=127.0.0.1 &
MYSQL_PID=$!

for _ in $(seq 1 60); do
  if mysqladmin ping -h127.0.0.1 --silent 2>/dev/null; then
    exit 0
  fi
  sleep 1
done

echo "MySQL failed to start" >&2
kill "$MYSQL_PID" 2>/dev/null || true
exit 1
