# Field-service repeat-visit risk model

This directory holds the data and a reference pipeline for a repeat-visit risk model.
The model estimates, for each open repair ticket, a calibrated probability that it needs
a repeat truck-roll within thirty days and turns that into a cost-optimal senior-dispatch
decision plus the supporting model artifacts. The data is in `data/service_ledger.csv`;
`data/equipment_class_reference.csv` and `data/dispatch_channel_catalog.csv` are lookup
tables, `data/data_dictionary.csv` names each field and its modeling role, and
`data/README.md` describes the files. The input columns are documented in `contracts/schema.md` and the required artifacts in
`contracts/output_contract.md`. The analysis entry point is `analysis.R`, which sources
the helpers under `fskit/`.
