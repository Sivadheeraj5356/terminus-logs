# Route Policy

Public routes:
- GET /v1/public/ping
- GET /v1/public/docs

Protected routes:
- GET /v1/admin/profile
- GET /v1/admin/audit

Protected routes must require bearer auth under canonical and non-canonical path variants.
