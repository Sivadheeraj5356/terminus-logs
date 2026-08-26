# Data files

- `service_ledger.csv` — one row per repair ticket, the modeling table. `repeat_visit`
  is the target and is blank on the open tickets in the newest `service_month`.
- `data_dictionary.csv` — each field, its type, and its role in the repeat-visit model.
- `equipment_class_reference.csv` — reference table of equipment classes.
- `dispatch_channel_catalog.csv` — reference table of dispatch channels.

Column definitions are in `../contracts/schema.md`; the required model outputs are in
`../contracts/output_contract.md`.
