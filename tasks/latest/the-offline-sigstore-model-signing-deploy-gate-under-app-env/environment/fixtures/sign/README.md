Sign-tree fixture inventory for the offline model-signing deploy gate.

| Tree | Role |
|------|------|
| `core.d/` | base model table |
| `sig.d/` | counter-sign restatements + `manifest.sx` |
| `appr.d/` | approval bump rows |
| `ovl.d/` | epoch overlay tables |
| `meta/` | epochs, revoke, cut, quorum configs |
| `certs.d/` | cert validity windows |
| `log.d/` | integrated-time journal |
| `witness/` | local observations (not a package input) |

Line formats: `/app/environment/docs/mx_rules.md`.
