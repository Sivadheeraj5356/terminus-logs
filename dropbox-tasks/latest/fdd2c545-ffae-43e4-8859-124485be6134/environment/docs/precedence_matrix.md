# Layer precedence

Layers rank from highest to lowest: **cli**, **env**, **manifest**, **default**.

## Scalar fields

`Restart`, `RestartSec`, and `Slice` take the value from the highest-ranking layer
that defines the field.

## List fields

`After`, `Requires`, and `Wants` use replacement: when the highest-ranking layer
that defines the field is found, its list replaces the entire field (no union merge).

## Fixture anchors

- `acme-worker.service`: cli sets `RestartSec=12`; env sets `Restart=always`.
- `acme-cache.service`: cli replaces `After` and `Requires` with `acme-collector.service` only.
- `acme-collector.service`: env sets `Slice=fleet.work.slice`.
