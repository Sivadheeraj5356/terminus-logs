A rollup node in /app runs a control plane that stakes validators, finalizes L2 blocks by weighted
committee endorsement, bridges L1 deposits into L2 balances, and runs governance referenda with
re-delegable ballots. Some safeguards no longer hold.

Probe the service as an attacker would; confirm each property and correct any that fails. A bridged
deposit becomes an irreversible L2 credit only once it sits the configured confirmation depth under the
L1 tip — not a block early, nor withheld once that deep. An applied deposit credits the
account it names as recipient, not the operator that relayed it. A re-delegated ballot votes only while
the account that shared it still holds the referendum. Operational statistics stay shut to a plain
participant. A failed login never betrays whether the username exists. A validator joins the active set
only when its integrity attestation verifies. No signing key or settlement credential appears in a
response, and none of these — nor a session credential — is ever written to /app/audit.log. One
network's validators stay invisible to accounts in another.

Password login yields the bearer token; /app/docs/api.md is the binding contract. The binary comes from
cargo build --release --locked and serves 127.0.0.1:8847.
