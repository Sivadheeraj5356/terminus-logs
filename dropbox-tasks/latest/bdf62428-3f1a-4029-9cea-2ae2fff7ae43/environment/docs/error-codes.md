# Error Codes Reference

All error messages are written to **stdout**. The process exits with code **1** on error.

## add-agent

| Condition          | Message                              |
|--------------------|--------------------------------------|
| Invalid tier value | `invalid tier: <tier>`               |
| Duplicate agent_id | `agent already exists: <agent_id>`   |

## open-ticket

| Condition             | Message                                  |
|-----------------------|------------------------------------------|
| Invalid priority value| `invalid priority: <priority>`           |
| Duplicate ticket_id   | `ticket already exists: <ticket_id>`     |

## resolve-ticket

| Condition                    | Message                                     |
|------------------------------|---------------------------------------------|
| Ticket does not exist        | `ticket not found: <ticket_id>`             |
| Ticket status is not 'open'  | `ticket already resolved: <ticket_id>`      |
| Agent does not exist         | `agent not found: <agent_id>`               |

Validation order: ticket existence → ticket status → agent existence.

## chain-verify

| Condition                 | Message (one per tampered row) |
|---------------------------|-------------------------------|
| Hash mismatch or bad chain| `TAMPERED <chain_id>`         |

Exit 1 if any row is tampered, exit 0 if chain is clean.

## General

- Unknown command: message printed to **stderr**, exit 1.
- Missing arguments: message printed to **stderr**, exit 1.
- Database open/query errors: message printed to **stderr**, exit 1.
