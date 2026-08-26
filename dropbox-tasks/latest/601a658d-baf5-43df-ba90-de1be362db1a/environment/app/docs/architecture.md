# Architecture

The node is a standard-library Rust HTTP server (no external crates). A small thread pool accepts
connections; each request is parsed and dispatched to a resource handler that authenticates,
authorises, validates input, performs work against in-memory stores, and serialises a JSON response.

## Request lifecycle

```
server -> api::dispatch -> extract::authenticate -> <resource handler> -> stores
```

`server` parses the HTTP request and hands it to `api::dispatch`, which matches the method and path,
authenticates, and calls the resource handler. Handlers return a structured result that is serialised
by the `json` layer.

## Modules

| Module | Responsibility | Representative items |
|---|---|---|
| `server` | HTTP/1.1 parsing, dispatch entry, thread pool | `http`, `request`, `response` |
| `json` | Hand-rolled JSON parser and serializer | `value`, `parse`, `ser` |
| `api` | Endpoint table, per-resource handlers, and response views | `account_endpoints`, `validator_endpoints`, `block_endpoints`, `relayer_endpoints`, `referendum_endpoints`, `monitoring_endpoints`, `admin_endpoints`, `validator_view`, `block_view`, `deposit_view`, `referendum_view`, `delegation_view` |
| `auth` | Credential and bearer-token authentication | `authenticator`, `token_verifier`, `credential_store`, `account_status` |
| `authz` | Role and permission authorisation | `access_control`, `role_registry` |
| `validator` | Validator registration, attestation, and access | `provisioning`, `integrity_gate`, `integrity_verifier`, `validator_access`, `validator_status`, `canonical` |
| `stake` | Stake registration, effective power, threshold, and slashing | `registration`, `power_book`, `supermajority`, `slashing` |
| `consensus` | Block creation, endorsement admission, weighted tally, and finality | `block_service`, `proposer`, `endorsement_admission`, `endorser_eligibility`, `finality` |
| `endorsement` | Endorsement records and the effective endorser roster | `roster` |
| `relayer` | L1 deposit ingestion, confirmation accounting, reconciliation, and settlement | `deposit_service`, `deposit_admission`, `reconciler`, `settlement`, `settlement_credit`, `finality_gate` |
| `governance` | Referendum ballots, grants, delegation, and vote policy | `referendum_directory`, `delegation_resolver`, `delegation_status`, `seat_authority`, `vote_policy` |
| `middleware` | Per-request access screening | `access_guard` |
| `crypto` | SHA-256, password hashing, signatures, token minting | `sha256`, `hashing`, `signature`, `tokens` |
| `audit` | Append-only audit records and redaction | `audit_log`, `event_sanitizer`, `field_scrubber`, `redactor` |
| `monitoring` | Health and operational statistics | `health`, `stats`, `access` |
| `config` | Policy configuration and node secrets | `policy`, `secrets` |
| `store` | Shared application state and seed data | `state`, `seed` |
| `types` | Domain types shared across modules | `validator`, `block`, `deposit`, `account`, `network` |

## Validators, stake, and the active set

Each account has a role that grants a set of permissions. A validator is registered against a stake and
carries an integrity attestation and a server-side signing key. Activation verifies the attestation and
admits the validator to its network's active set with an effective power equal to its stake; slashing
zeroes that power and removes the validator from the active set. The active set is the authoritative
record of which validators currently participate.

## Blocks, endorsement, and finality

A block fixes a committee of active validators, recording each member's endorsement weight and the
committee's total power at creation time. Committee members endorse the block, and the consensus layer
tallies the weight of the members that have endorsed to decide whether the block has reached the
two-thirds threshold. Each distinct endorsing validator contributes its weight at most once regardless
of how many endorsement records it has, and the tally consults each endorser against the current
participation state so that a member which has left the active set no longer contributes weight. The
endorsement records themselves are retained in full and are exposed through the endorsements listing;
finality is assessed live when a block is read or an endorsement is recorded.

## L1 relayer and bridged deposits

The relayer records deposits observed on the base layer and reconciles them into L2 state. A deposit
carries the L1 block height at which it was observed and the network account it credits. Reconciliation
takes the observed L1 tip, decides which pending deposits are deep enough in the L1 chain to apply, and
marks those applied against the tip. Applying a deposit settles it into L2: the settlement layer credits
the recipient account's balance and appends a settlement record to the audit trail. The relayer is an
operator-plane surface; the confirmation-depth policy is part of the node's policy configuration.
Deposits are stored in the shared state alongside the observed tip per network.

## Referenda, grants, and delegation

Governance access to a referendum is held either directly — by ownership or a direct ballot grant — or
by re-delegation, where an account that holds a delegable grant shares access with a third account. The
`governance` layer resolves whether a caller may cast a vote, composing direct grants, delegations, and
the referendum's visibility. Direct grants and delegations are stored separately in the shared state.

## State

All stores are in-memory and guarded by read/write locks inside a single shared application state.
Networks and accounts are seeded at startup (see `docs/api.md`). Validators, blocks, endorsements,
deposits, referenda, grants, delegations, and votes are created at runtime through the API.
