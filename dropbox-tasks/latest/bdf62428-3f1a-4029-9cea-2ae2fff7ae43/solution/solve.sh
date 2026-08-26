#!/usr/bin/env bash
set -euo pipefail

# Complete implementation: all 3 milestones (init, add-agent, open-ticket,
# list-tickets, resolve-ticket, priority-report, agent-stats, chain-verify,
# sla-report, priority-stats, ticket-analytics)

rm -f /app/chain.go /app/config.go /app/constants.go /app/converter.go /app/db.go /app/errors.go /app/filters.go /app/logger.go /app/migrations.go /app/output.go /app/pagination.go /app/queries.go /app/sorting.go /app/stats.go /app/types.go /app/validate.go /app/version.go

cp "$(dirname "$0")/cmds.go" /app/cmds.go

cd /app && go build -o /app/app .
