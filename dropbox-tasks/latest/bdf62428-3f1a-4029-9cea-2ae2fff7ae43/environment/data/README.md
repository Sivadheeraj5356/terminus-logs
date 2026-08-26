# Seed Data

This directory contains sample data files for manual testing and demonstration.

## seed_agents.tsv

Tab-separated file with columns: `agent_id`, `name`, `tier`

To import:
```bash
while IFS=$'\t' read -r id name tier; do
    /app/app add-agent /tmp/demo.db "$id" "$name" "$tier"
done < /data/seed_agents.tsv
```

## seed_tickets.tsv

Tab-separated file with columns: `ticket_id`, `title`, `priority`

To import:
```bash
while IFS=$'\t' read -r id title priority; do
    /app/app open-ticket /tmp/demo.db "$id" "$title" "$priority"
done < /data/seed_tickets.tsv
```

These files are provided for reference only and are not used by the verifier tests.
