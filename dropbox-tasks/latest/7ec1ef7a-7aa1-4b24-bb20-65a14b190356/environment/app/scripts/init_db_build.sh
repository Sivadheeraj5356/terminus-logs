#!/bin/bash
set -euo pipefail

install -d -o mysql -g mysql /var/run/mysqld
mariadb-install-db --user=mysql --datadir=/var/lib/mysql > /dev/null

mariadbd --user=mysql &
pid=$!

for _ in $(seq 1 60); do
  if mariadb-admin ping --silent 2>/dev/null; then
    break
  fi
  sleep 1
done

mariadb-admin ping --silent

mariadb -uroot < /app/priv/sql/init.sql
mariadb -uroot helix_catalog < /app/priv/sql/seed.sql

mariadb-admin shutdown
wait "$pid"
