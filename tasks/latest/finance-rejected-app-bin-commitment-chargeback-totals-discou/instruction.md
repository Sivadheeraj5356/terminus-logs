Finance rejected /app/bin/commitment-chargeback. Totals discounts pool shares and report digest disagree and reruns are not byte identical.

Edit only commitment.go ratecard.go intake.go and main.go under /app/carrydown_engine. Leave all other carrydown_engine files and leave /app/pledge_inputs and /app/billing_contracts byte identical write protected. Writes touch only /app/output/ledger.json. Rebuild with go build to /app/bin/commitment-chargeback as a Linux ELF using stdlib only. main.go keeps bare /app/pledge_inputs and /app/output constants. Delete Makefile json and C junk. Follow /app/billing_contracts/SCHEMA.md for all billing rules.

Ledger matches SCHEMA serialization and recomputation with conserved summary rollups and byte-identical fresh builds and consecutive reruns.
