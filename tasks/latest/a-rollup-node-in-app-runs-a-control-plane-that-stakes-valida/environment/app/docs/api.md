# keystone API reference

All endpoints are served over HTTP/1.1 on `127.0.0.1:8847` by default (`KEYSTONE_ADDR` overrides the
bind address; `KEYSTONE_AUDIT_PATH` overrides the audit-log path, default `/app/audit.log`). Request
and response bodies are JSON. Unless noted otherwise, an endpoint requires authentication.

## Authentication and authorization

Authenticate with `POST /v1/auth/token`, then send the returned token as `Authorization: Bearer
<token>` on every protected request. A request with a missing or unrecognised token is rejected with
`401` or `403`. A failed login does not reveal whether the account exists: authenticating an unknown
username and authenticating a known account with the wrong password both fail with the same status
code and the same error code.

Every account has a role — `participant`, `operator`, or `admin` — and belongs to exactly one network.
Permissions follow least privilege. Operational and administrative endpoints require an elevated role;
ordinary resource endpoints are available to participants. A resource is visible only within its owning
network: an account of another network is refused even when its role would otherwise permit the read.

Error responses have the shape `{"error": {"code": "<code>", "message": "<text>"}}` and never carry
internal diagnostics, stack traces, or secrets.

### Seed accounts

| username | password | network | role |
|---|---|---|---|
| alice | alice-pw-9f3 | network-alpha | participant |
| carol | carol-pw-7c2 | network-alpha | participant |
| dave | dave-pw-2k9 | network-alpha | participant |
| erin | erin-pw-6m4 | network-alpha | operator |
| bob | bob-pw-4a1 | network-beta | participant |
| opsuser | ops-pw-3d7 | network-ops | operator |
| root | root-pw-1b8 | network-ops | admin |

## Health

`GET /v1/health` — public, no authentication. Returns `200` with `{"status": "ok", "service":
"keystone"}`.

## Auth

`POST /v1/auth/token`
- Body: `{"username": string, "password": string}`
- `200`: `{"token": string, "account_id": string, "network_id": string, "role": string, "expires_at":
  number}`
- `401`/`403`: authentication failed (identical response for unknown username and wrong password).

`GET /v1/account`
- `200`: `{"id": string, "username": string, "network_id": string, "network_name": string, "role":
  string, "status": string, "l2_balance": number}`. `l2_balance` is the account's L2 balance, the
  running sum of the amounts of the bridged deposits that name it as recipient and have been applied.

## Validators

A validator is registered by an account, carries a stake, and is admitted to the network's active set
by activation once its integrity attestation verifies. Each validator holds a long-lived signing key
that is generated server-side and **never** appears in any API response or audit record. Activation
issues a one-time session credential returned only in the activation response.

`POST /v1/validators` (role: participant or above)
- Body: `{"name": string, "stake"?: number >= 1, "attested"?: bool}`. `stake` defaults to the
  configured minimum; `attested` defaults to `true`. A validator registered with `"attested": false`
  carries no attestation.
- `201`: validator detail (see below).

`GET /v1/validators`
- `200`: `{"validators": [{"id": string, "name": string, "status": string, "effective_power":
  number}]}` for the caller's network.

`GET /v1/validators/{id}`
- `200`: validator detail. `403` if the validator belongs to another network.

Validator detail: `{"id": string, "network_id": string, "owner_id": string, "name": string, "stake":
number, "effective_power": number, "status": string, "attested": bool, "created_at": number}`. Status
is one of `registered`, `active`, `slashed`. The signing key and session credential are never included.

`POST /v1/validators/{id}/activate` (role: owner, or operator/admin in the network)
- Verifies the validator's integrity attestation, admits it to the active set, and issues its session
  credential.
- `200`: `{"validator": <validator detail>, "session_credential": string}`.
- `422` (`validator_unattested` / `validator_untrusted`): the validator carries no attestation, or the
  attestation does not verify, so it is refused admission.

`POST /v1/validators/{id}/slash` (role: operator or admin)
- Zeroes the validator's effective power and removes it from the active set (status becomes `slashed`).
- `200`: validator detail.

## Blocks and endorsement

A block is a unit of L2 chain data proposed by an active validator against an explicit committee of
active validators. Each committee member is recorded with the voting weight (its stake) it held when
the block was created; the committee's total power is the sum of those weights. Committee members
endorse the block, and a block is **finalized** once the combined weight of the endorsing members
reaches the two-thirds threshold: `threshold_power = ceil(2 * total_power / 3)`.

Endorsement is counted per **distinct** validator. A committee member's weight contributes to
`endorsed_power` at most once, no matter how many times that validator endorses the block, and only
while the validator is still in the network's active set. `endorser_count` is the number of distinct
validators that have endorsed. So a single validator that endorses repeatedly cannot raise
`endorsed_power` beyond its own weight, and a block is finalized only when distinct endorsers whose
combined stake meets the threshold have endorsed it.

`POST /v1/blocks` (role: participant or above)
- Body: `{"proposer_validator_id": string, "parent_hash"?: string, "height": number >= 0, "committee":
  [string, ...], "payload"?: string}`. `parent_hash` defaults to `"genesis"`. The proposer must be an
  active validator owned by the caller in the caller's network; every committee id must be an active
  validator in the caller's network. An empty committee is rejected.
- `201`: block detail (see below).

`GET /v1/blocks`
- `200`: `{"blocks": [{"id": string, "parent_hash": string, "height": number, "total_power": number,
  "endorser_count": number}]}` for the caller's network.

`GET /v1/blocks/{id}`
- `200`: block detail, with finality assessed live against the current active set.

`POST /v1/blocks/{id}/endorsements` (role: participant or above)
- Body: `{"validator_id": string}`. The validator must be an active validator owned by the caller and a
  member of the block committee.
- `201`: block detail, with the endorsement recorded.

`GET /v1/blocks/{id}/endorsements`
- `200`: `{"endorsements": [string, ...], "endorser_count": number}`. `endorsements` lists every
  endorsement record (a validator that endorsed twice appears twice); `endorser_count` is the number of
  distinct endorsing validators.

Block detail: `{"id": string, "network_id": string, "parent_hash": string, "proposer_account_id":
string, "proposer_validator_id": string, "height": number, "payload_hash": string, "committee":
[{"validator_id": string, "weight": number}], "endorsements": [string], "endorser_count": number,
"total_power": number, "endorsed_power": number, "threshold_power": number, "finalized": bool,
"created_at": number}`. `endorsed_power` is the combined weight of the distinct active committee members
that have endorsed, and `finalized` is `endorsed_power >= threshold_power`.

## L1 relayer and bridged deposits

The node bridges deposits observed on the base layer (L1) into L2 state. The relayer is part of the
operator plane: every relayer endpoint requires the operator or admin role. A deposit is an L1 event
observed at a specific L1 block height and destined for an account in the caller's network. A deposit
is recorded `pending` and becomes `applied` (irreversibly credited to L2) only once it is deep enough
in the L1 chain to survive a reorg.

Finality is governed by a confirmation depth (`finality_depth`, default `12`). A deposit observed at L1
height `H` requires at least `finality_depth` L1 blocks built **strictly on top of** `H` before it may
be applied: with the observed L1 tip at height `T`, the deposit is applied only when `T - H >=
finality_depth`. A deposit with fewer confirmations than the depth must remain `pending`, because an L1
reorg shallower than the depth could still remove it — applying it early would let a reverted L1 deposit
stand as an L2 credit. Application is idempotent and monotonic: an applied deposit stays applied.

`POST /v1/relayer/deposits` (role: operator or admin)
- Body: `{"l1_height": number >= 1, "recipient_account_id": string, "amount": number >= 1}`. The
  recipient must be an account in the caller's network. Records a pending deposit.
- `201`: deposit detail (see below).
- `400`: `l1_height` or `amount` is not a positive integer. `422` (`unknown_recipient` /
  `foreign_recipient`): the recipient does not exist or belongs to another network.

`GET /v1/relayer/deposits`
- `200`: `{"deposits": [{"id": string, "l1_height": number, "amount": number, "status": string}]}` for
  the caller's network.

`GET /v1/relayer/deposits/{id}`
- `200`: deposit detail. `404` if the deposit belongs to another network.

Deposit detail: `{"id": string, "network_id": string, "owner_id": string, "l1_height": number,
"recipient_account_id": string, "amount": number, "status": "pending" | "applied", "applied_at_tip":
number | null, "finalized": bool, "created_at": number}`. `finalized` is `true` exactly when `status`
is `applied`; `applied_at_tip` is the observed L1 tip at which the deposit was applied, or `null` while
pending.

`POST /v1/relayer/reconcile` (role: operator or admin)
- Body: `{"l1_tip": number >= 0}`. Records the observed L1 tip height and applies every pending deposit
  in the caller's network that has reached the finality depth against that tip. A deposit whose
  confirmations (`l1_tip - l1_height`) are below `finality_depth` is left pending.
- Applying a deposit settles it: the deposit's `amount` is credited to the L2 balance of its recipient
  account and a `relayer.settle` audit record is appended. Settlement issues a one-time settlement
  credential that is recorded server-side and never returned or written to the log.
- `200`: `{"network_id": string, "l1_tip": number, "finality_depth": number, "applied_count": number,
  "applied": [{"id": string, "l1_height": number, "confirmations": number}]}`. Every entry in `applied`
  has `confirmations >= finality_depth`.

`GET /v1/relayer/status` (role: operator or admin)
- `200`: `{"network_id": string, "l1_tip": number, "finality_depth": number, "deposit_count": number,
  "applied_deposit_count": number, "pending_deposit_count": number}` for the caller's network.

## Governance referenda

A referendum is owned by the account that creates it and has a visibility of `private` or `public`.
Casting a governance vote requires access, which is held by the owner, by a direct ballot grant, by a
re-delegation whose delegator still holds the referendum, or — for a public referendum — by the broad
governance role.

`POST /v1/referenda` (role: participant or above)
- Body: `{"title": string, "visibility"?: "private" | "public"}` (default `private`).
- `201`: `{"id": string, "network_id": string, "owner_id": string, "title": string, "visibility":
  string, "created_at": number}`.

`GET /v1/referenda`
- `200`: `{"referenda": [{"id": string, "title": string, "visibility": string}]}` for the caller's
  network.

`GET /v1/referenda/{id}`
- `200`: referendum detail.

`POST /v1/referenda/{id}/grants` (owner, or operator/admin in the network)
- Body: `{"subject_account_id": string, "may_delegate"?: bool}` (default `false`).
- `201`: `{"referendum_id": string, "subject_account_id": string, "may_delegate": bool}`.

`GET /v1/referenda/{id}/grants`
- `200`: `{"grants": [{"subject_account_id": string, "may_delegate": bool}]}`.

`DELETE /v1/referenda/{id}/grants/{account_id}` (owner, or operator/admin)
- `200`: `{"referendum_id": string, "subject_account_id": string, "revoked": true}`.

`POST /v1/referenda/{id}/delegations` (a grantee that holds a delegable grant)
- Body: `{"subject_account_id": string}`. The caller must hold a ballot grant with `may_delegate` true;
  the subject must be an account in the same network.
- `201`: `{"referendum_id": string, "subject_account_id": string}`.

`GET /v1/referenda/{id}/delegations`
- `200`: `{"delegations": [{"referendum_id": string, "subject_account_id": string, "delegated_by":
  string, "active": bool}]}`. A delegation is `active` only while the account that issued it still holds
  the referendum; revoking the delegator's grant flips its delegations to inactive.

`POST /v1/referenda/{id}/votes` (role: participant or above, subject to vote access)
- Body: `{"choice"?: string}` (default `"aye"`).
- `201`: `{"referendum_id": string, "choice": string, "recorded": true}`.
- `403`: the caller does not hold vote access (including a delegated ballot whose delegator has since
  lost the referendum).

`GET /v1/referenda/{id}/votes` (owner, or operator/admin)
- `200`: `{"votes": [{"account_id": string, "choice": string}]}`.

## Monitoring

`GET /v1/monitoring/stats` (role: operator or admin only)
- `200`: `{"network_id": string, "validator_count": number, "active_validator_count": number,
  "block_count": number, "referendum_count": number, "deposit_count": number, "applied_deposit_count":
  number}` for the caller's network.
- `403`: a participant is refused, even though it can read its own blocks and validators.

## Administration

`POST /v1/admin/accounts/{username}/suspend` (role: admin)
- `200`: `{"username": string, "status": "suspended"}`. Only accounts in the caller's network.

`GET /v1/admin/audit?limit=<n>` (role: operator or admin)
- `200`: `{"records": [{"timestamp": number, "identity": string, "client_addr": string, "operation":
  string, "target": string, "result": string, "detail": object}]}`. Sensitive keys are stripped from
  `detail` before it is returned.

## Audit log

Security-relevant operations are appended as JSON lines to `/app/audit.log`. Each record is
`{"timestamp": number, "identity": string, "client_addr": string, "operation": string, "target":
string, "result": string, "detail": object, "signature": string}`. Operations include
`validator.register`, `validator.activate`, `validator.slash`, `block.create`, `block.endorse`,
`relayer.ingest`, `relayer.reconcile`, `relayer.settle`, `referendum.create`, `referendum.grant`,
`referendum.revoke`, `referendum.delegate`, `referendum.vote`, `account.suspend`, and `auth.failed`.
Secret material — including validator signing keys, issued session credentials, and settlement
credentials — is stripped from `detail` before a record is written to disk and never appears in the log.

A `relayer.settle` record targets the applied deposit id, and its `detail` contains exactly
`{"deposit_id": string, "beneficiary_account_id": string, "ingested_by": string, "amount": number,
"settled_at_tip": number}`: `beneficiary_account_id` is the credited recipient account and `ingested_by`
is the operator account that relayed the deposit. The settlement credential is not among the persisted
keys.
