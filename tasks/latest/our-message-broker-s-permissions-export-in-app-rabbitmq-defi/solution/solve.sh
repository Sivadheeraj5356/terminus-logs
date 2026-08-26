#!/bin/bash
set -euo pipefail

# Oracle solution: brings /app/rabbitmq_definitions.json into compliance with
# /app/RABBITMQ_ACCESS_POLICY.md, cross-referencing /app/PERMISSION_CHANGELOG.md,
# /app/DOWNSTREAM_CONSUMERS.md, /app/PROTECTED_SERVICE_ACCOUNTS.md, and
# /app/INCIDENT_ACCESS.md. Always rebuilds from the pristine backup at
# /app/.rabbitmq_definitions.orig.json rather than whatever is currently in
# /app/rabbitmq_definitions.json, so running it any number of times produces
# an identical result (idempotent).

python3 - << 'PY'
import json
import shutil

SRC = "/app/.rabbitmq_definitions.orig.json"
DST = "/app/rabbitmq_definitions.json"
shutil.copyfile(SRC, DST)

with open(DST) as f:
    data = json.load(f)

# Fully rewritten from the tier table + documented overrides + permission
# changelog (latest-dated entry per (user, vhost, capability) wins, valid
# vhosts only) + time-boxed incident access (evaluated as of 2026-07-16) +
# the two independent confidential-tier budgets; users/vhosts are left
# exactly as seeded.
data["permissions"] = [
    {"user": "svc-billing-api", "vhost": "/billing", "configure": r"^billing\..*", "write": r"^billing\..*", "read": r"^billing\..*"},
    {"user": "svc-billing-api", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-billing-worker", "vhost": "/billing", "configure": "", "write": r"^billing\..*", "read": r"^billing\..*"},
    {"user": "svc-billing-worker", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-payments-gateway", "vhost": "/billing", "configure": "", "write": "", "read": r"^billing\.legacy-invoices$"},
    {"user": "svc-payments-gateway", "vhost": "/payments", "configure": r"^payments\..*", "write": r"^payments\..*", "read": r"^payments\..*"},
    {"user": "svc-payments-gateway", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-payments-recon", "vhost": "/payments", "configure": "", "write": "", "read": r"^payments\..*"},
    {"user": "svc-payments-recon", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-audit-collector", "vhost": "/payments", "configure": "", "write": r"^payments\.dispute-notes$", "read": r"^payments\..*"},
    {"user": "svc-audit-collector", "vhost": "/audit-log", "configure": r"^audit-log\..*", "write": r"^audit-log\..*", "read": r"^audit-log\..*"},
    {"user": "svc-audit-collector", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-orders-api", "vhost": "/orders", "configure": r"^orders\..*", "write": r"^orders\..*", "read": r"^orders\..*"},
    {"user": "svc-orders-api", "vhost": "/reporting", "configure": "", "write": "", "read": r"^reporting\..*"},
    {"user": "svc-orders-api", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-fulfillment-worker", "vhost": "/fulfillment", "configure": r"^fulfillment\..*", "write": r"^fulfillment\..*", "read": r"^fulfillment\..*"},
    {"user": "svc-fulfillment-worker", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-reporting-etl", "vhost": "/reporting", "configure": r"^reporting\..*", "write": r"^reporting\..*", "read": r"^reporting\..*"},
    {"user": "svc-reporting-etl", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},

    {"user": "svc-public-status-writer", "vhost": "/public-status", "configure": r"^public-status\..*", "write": r"^public-status\..*", "read": r"^public-status\..*"},

    {"user": "svc-incident-responder", "vhost": "/orders", "configure": "", "write": r"^orders\..*", "read": r"^orders\..*"},
    {"user": "svc-incident-responder", "vhost": "/public-status", "configure": "", "write": "", "read": r"^public-status\..*"},
]

with open(DST, "w") as f:
    json.dump(data, f, indent=2)
    f.write("\n")
PY
