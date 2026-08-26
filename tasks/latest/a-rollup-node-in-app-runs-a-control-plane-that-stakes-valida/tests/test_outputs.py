import json
import os
import shutil
import signal
import subprocess
import tempfile
import time
import uuid

import pytest
import requests

APP_DIR = "/app"
AUDIT_PATH = "/app/audit.log"
PORT = 8847
BASE = f"http://127.0.0.1:{PORT}"

TCP_LISTEN = "0A"

_S = uuid.uuid4().hex[:8]

SEED = {
    "alice": ("alice", "alice-pw-9f3"),
    "carol": ("carol", "carol-pw-7c2"),
    "dave": ("dave", "dave-pw-2k9"),
    "erin": ("erin", "erin-pw-6m4"),
    "bob": ("bob", "bob-pw-4a1"),
    "opsuser": ("opsuser", "ops-pw-3d7"),
    "root": ("root", "root-pw-1b8"),
}


def _listening_pids(port):
    """Return the pid of every process holding a listening TCP socket on `port`.

    Read straight from /proc so the answer covers a leftover process whatever its
    command line, and needs no external tool.
    """
    inodes = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            with open(table) as handle:
                rows = handle.read().splitlines()[1:]
        except OSError:
            continue
        for row in rows:
            columns = row.split()
            if len(columns) < 10 or columns[3] != TCP_LISTEN:
                continue
            if int(columns[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(columns[9])
    if not inodes:
        return set()

    pids = set()
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        descriptors = os.path.join("/proc", entry, "fd")
        try:
            names = os.listdir(descriptors)
        except OSError:
            continue
        for name in names:
            try:
                target = os.readlink(os.path.join(descriptors, name))
            except OSError:
                continue
            if target.startswith("socket:[") and target[len("socket:[") : -1] in inodes:
                pids.add(int(entry))
                break
    return pids


def _free_port(port):
    """Terminate, then kill, whatever already listens on `port`.

    A node the agent left running would otherwise keep the port and answer every
    assertion in place of the binary built here.
    """
    for signum in (signal.SIGTERM, signal.SIGKILL):
        holders = _listening_pids(port) - {os.getpid()}
        if not holders:
            return
        for pid in holders:
            try:
                os.kill(pid, signum)
            except OSError:
                pass
        for _ in range(20):
            time.sleep(0.25)
            if not _listening_pids(port):
                return


def _build_keystone(build_dir):
    """Compile /app/src into `build_dir` and return the release binary it produced.

    CARGO_TARGET_DIR is set here so the binary under test is the one compiled now
    from the agent's source, never an artifact left at the conventional target path.
    """
    env = dict(os.environ)
    env["CARGO_TARGET_DIR"] = build_dir
    build = subprocess.run(
        ["cargo", "build", "--release", "--locked"],
        cwd=APP_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    assert build.returncode == 0, f"cargo build failed:\n{build.stderr}"
    binary = os.path.join(build_dir, "release", "keystone")
    assert os.path.isfile(binary), f"cargo did not produce {binary}"
    return binary


@pytest.fixture(scope="session", autouse=True)
def server():
    """Build the keystone rollup node from the current source and run it for the suite.

    The verifier compiles /app/src into a private target directory, frees
    127.0.0.1:8847 of any process left listening on it, spawns the binary it just
    built, and refuses to continue unless that very process owns the port. Every
    assertion therefore reflects the code under audit rather than a prebuilt artifact
    or a node the agent left running. No listen address or audit path is injected:
    the binary has to bind its documented default of 127.0.0.1:8847 and write its
    documented audit log at /app/audit.log on its own.
    """
    build_dir = tempfile.mkdtemp(prefix="keystone-verifier-")
    binary = _build_keystone(build_dir)
    log_path = os.path.join(build_dir, "keystone.log")

    env = dict(os.environ)
    env.pop("KEYSTONE_ADDR", None)
    env.pop("KEYSTONE_AUDIT_PATH", None)

    proc = None
    problem = None
    for _ in range(3):
        _free_port(PORT)
        holders = _listening_pids(PORT)
        if holders:
            problem = f"port {PORT} is held by process(es) {sorted(holders)} and could not be freed"
            continue

        if os.path.exists(AUDIT_PATH):
            os.remove(AUDIT_PATH)

        with open(log_path, "w") as log:
            proc = subprocess.Popen([binary], env=env, stdout=log, stderr=subprocess.STDOUT)

        ready = False
        for _ in range(60):
            if proc.poll() is not None:
                break
            try:
                if requests.get(f"{BASE}/v1/health").status_code == 200:
                    ready = True
                    break
            except requests.RequestException:
                pass
            time.sleep(0.5)

        if proc.poll() is not None:
            with open(log_path) as log:
                output = log.read().strip()
            problem = (
                f"the node built from {APP_DIR}/src exited with status {proc.returncode} "
                f"instead of serving 127.0.0.1:{PORT}: {output}"
            )
            proc = None
            continue

        if not ready:
            proc.kill()
            proc.wait()
            problem = f"the node built from {APP_DIR}/src never became healthy on 127.0.0.1:{PORT}"
            proc = None
            continue

        owners = _listening_pids(PORT)
        if owners != {proc.pid}:
            proc.kill()
            proc.wait()
            problem = (
                f"127.0.0.1:{PORT} is served by process(es) {sorted(owners)}, not by the "
                f"node built from {APP_DIR}/src (pid {proc.pid}); the suite grades only "
                f"the binary it built"
            )
            proc = None
            continue

        problem = None
        break

    if proc is None:
        shutil.rmtree(build_dir, ignore_errors=True)
        pytest.fail(problem)

    yield

    proc.kill()
    proc.wait()
    shutil.rmtree(build_dir, ignore_errors=True)


def _login_json(user):
    username, password = SEED[user]
    r = requests.post(f"{BASE}/v1/auth/token", json={"username": username, "password": password})
    assert r.status_code == 200, f"login {user} failed: {r.status_code} {r.text}"
    return r.json()


def login(user):
    return _login_json(user)["token"]


def account_id(user):
    return _login_json(user)["account_id"]


def auth(token):
    return {"authorization": f"Bearer {token}"}


def account_info(token):
    r = requests.get(f"{BASE}/v1/account", headers=auth(token))
    assert r.status_code == 200, f"get account failed: {r.status_code} {r.text}"
    return r.json()


def new_validator(token, stake=1, attested=True, activate=True):
    body = {"name": f"v-{_S}-{uuid.uuid4().hex[:6]}", "stake": stake, "attested": attested}
    r = requests.post(f"{BASE}/v1/validators", headers=auth(token), json=body)
    assert r.status_code == 201, f"validator register failed: {r.status_code} {r.text}"
    validator_id = r.json()["id"]
    if activate:
        a = requests.post(f"{BASE}/v1/validators/{validator_id}/activate", headers=auth(token), json={})
        assert a.status_code == 200, f"validator activate failed: {a.status_code} {a.text}"
    return validator_id


def create_block(token, proposer, committee, height, parent_hash="genesis"):
    body = {
        "proposer_validator_id": proposer,
        "parent_hash": parent_hash,
        "committee": committee,
        "height": height,
    }
    return requests.post(f"{BASE}/v1/blocks", headers=auth(token), json=body)


def endorse_block(token, block_id, validator_id):
    return requests.post(
        f"{BASE}/v1/blocks/{block_id}/endorsements",
        headers=auth(token),
        json={"validator_id": validator_id},
    )


def get_block(token, block_id):
    r = requests.get(f"{BASE}/v1/blocks/{block_id}", headers=auth(token))
    assert r.status_code == 200, f"get block failed: {r.status_code} {r.text}"
    return r.json()


def relayer_status(token):
    r = requests.get(f"{BASE}/v1/relayer/status", headers=auth(token))
    assert r.status_code == 200, f"relayer status failed: {r.status_code} {r.text}"
    return r.json()


def ingest_deposit(token, l1_height, recipient, amount=5):
    return requests.post(
        f"{BASE}/v1/relayer/deposits",
        headers=auth(token),
        json={"l1_height": l1_height, "recipient_account_id": recipient, "amount": amount},
    )


def reconcile(token, l1_tip):
    r = requests.post(f"{BASE}/v1/relayer/reconcile", headers=auth(token), json={"l1_tip": l1_tip})
    assert r.status_code == 200, f"reconcile failed: {r.status_code} {r.text}"
    return r.json()


def get_deposit(token, deposit_id):
    r = requests.get(f"{BASE}/v1/relayer/deposits/{deposit_id}", headers=auth(token))
    assert r.status_code == 200, f"get deposit failed: {r.status_code} {r.text}"
    return r.json()


def create_referendum(token, title, visibility="private"):
    r = requests.post(
        f"{BASE}/v1/referenda",
        headers=auth(token),
        json={"title": title, "visibility": visibility},
    )
    assert r.status_code == 201, f"referendum create failed: {r.status_code} {r.text}"
    return r.json()["id"]


def grant_ballot(owner_token, referendum_id, account, may_delegate=False):
    return requests.post(
        f"{BASE}/v1/referenda/{referendum_id}/grants",
        headers=auth(owner_token),
        json={"subject_account_id": account, "may_delegate": may_delegate},
    )


def revoke_ballot(owner_token, referendum_id, account):
    return requests.delete(
        f"{BASE}/v1/referenda/{referendum_id}/grants/{account}",
        headers=auth(owner_token),
    )


def create_delegation(delegator_token, referendum_id, account):
    return requests.post(
        f"{BASE}/v1/referenda/{referendum_id}/delegations",
        headers=auth(delegator_token),
        json={"subject_account_id": account},
    )


def list_delegations(token, referendum_id):
    r = requests.get(f"{BASE}/v1/referenda/{referendum_id}/delegations", headers=auth(token))
    assert r.status_code == 200, f"list delegations failed: {r.status_code} {r.text}"
    return r.json()["delegations"]


def cast_gov_vote(token, referendum_id, choice="aye"):
    return requests.post(
        f"{BASE}/v1/referenda/{referendum_id}/votes",
        headers=auth(token),
        json={"choice": choice},
    )


def looks_like_credential(value):
    return (
        isinstance(value, str)
        and len(value) == 48
        and all(c in "0123456789abcdef" for c in value)
    )


def all_keys(obj):
    keys = set()
    if isinstance(obj, dict):
        for key, value in obj.items():
            keys.add(key)
            keys |= all_keys(value)
    elif isinstance(obj, list):
        for item in obj:
            keys |= all_keys(item)
    return keys


def all_values(obj):
    out = []
    if isinstance(obj, dict):
        for value in obj.values():
            out += all_values(value)
    elif isinstance(obj, list):
        for item in obj:
            out += all_values(item)
    else:
        out.append(obj)
    return out


def audit_records():
    assert os.path.exists(AUDIT_PATH), "audit log was not written"
    records = []
    with open(AUDIT_PATH) as handle:
        for line in handle.read().splitlines():
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


def test_health_is_public():
    """The health endpoint is reachable without authentication and reports the service status."""
    r = requests.get(f"{BASE}/v1/health")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_unauthenticated_requests_are_rejected():
    """Protected endpoints reject a missing or unrecognised bearer token with 401 or 403."""
    r = requests.get(f"{BASE}/v1/validators")
    assert r.status_code in (401, 403)
    r = requests.get(f"{BASE}/v1/validators", headers=auth("not-a-real-token"))
    assert r.status_code in (401, 403)


def test_deposit_settles_exactly_at_the_confirmation_depth():
    """A bridged L1 deposit becomes an applied L2 credit as soon as it is buried the configured finality
    depth under the observed L1 tip: with the tip at height T and a deposit observed at L1 height H, the
    deposit is applied once T - H reaches the depth. An operator ingests a deposit and reconciles with a
    tip that puts it exactly at the depth. The deposit must be applied — it must appear in the reconcile's
    applied set and read back as applied. A node that measures the finalized frontier one L1 block too
    conservatively (counting the deposit's own block toward the depth) strands a deposit that L1 has
    already confirmed to the required depth, so it withholds a credit that policy says is safe to release.
    This is the entry to the settlement flow: until the deposit applies, nothing downstream of it runs."""
    operator = login("erin")
    depth = relayer_status(operator)["finality_depth"]
    assert depth >= 2, f"finality depth is too small to test the boundary: {depth}"

    recipient = account_id("alice")
    height = 500000
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=6)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]
    assert created.json()["status"] == "pending"

    tip = height + depth
    outcome = reconcile(operator, tip)
    applied_ids = [entry["id"] for entry in outcome["applied"]]
    assert deposit_id in applied_ids, (
        f"a deposit with a full {depth} confirmations was not applied: it had {tip - height} "
        f"confirmations against a depth of {depth} but was withheld"
    )

    after = get_deposit(operator, deposit_id)
    assert after["status"] == "applied", "a deposit at exactly the finality depth was not applied"
    assert after["finalized"] is True


def test_deposit_below_depth_stays_pending():
    """Reconciliation itself is correct below the boundary: a deposit one confirmation short of the depth
    is left pending. This holds on both the buggy and the fixed node, so it isolates the withholding of a
    deposit that has exactly reached the depth, rather than deposit application in general, as the defect
    behind the tightening test."""
    operator = login("erin")
    depth = relayer_status(operator)["finality_depth"]

    recipient = account_id("alice")
    height = 500100
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=3)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]

    tip = height + depth - 1
    outcome = reconcile(operator, tip)
    applied_ids = [entry["id"] for entry in outcome["applied"]]
    assert deposit_id not in applied_ids, (
        f"a deposit was applied one confirmation early: {tip - height} confirmations against depth {depth}"
    )
    after = get_deposit(operator, deposit_id)
    assert after["status"] == "pending", "a deposit below the finality depth was applied"


def test_settlement_credits_the_recipient_not_the_operator():
    """Applying a bridged deposit credits its amount to the L2 balance of the account named as the
    deposit's recipient, never the operator account that relayed the deposit. An operator ingests a
    deposit for a participant recipient and reconciles at the finality depth; the recipient's L2 balance
    must rise by the deposit amount, and the settlement record must name the recipient as beneficiary.
    Because a deposit that is not applied is never settled, this credit is observable only once the deposit
    reaches the finality depth and is applied."""
    operator = login("erin")
    depth = relayer_status(operator)["finality_depth"]

    recipient_token = login("carol")
    recipient = account_id("carol")
    before = account_info(recipient_token)["l2_balance"]

    height = 500200
    amount = 9
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=amount)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]

    reconcile(operator, height + depth)

    after = account_info(recipient_token)["l2_balance"]
    assert after - before == amount, (
        "an applied deposit did not credit its recipient's L2 balance by the deposit amount: "
        f"balance moved from {before} to {after}, expected +{amount}. The credit was diverted from the "
        "recipient (most likely to the operator that relayed the deposit)"
    )

    settle = [
        event
        for event in audit_records()
        if event.get("operation") == "relayer.settle" and event.get("target") == deposit_id
    ]
    assert settle, f"the settlement of {deposit_id} was not recorded"
    assert settle[-1]["detail"].get("beneficiary_account_id") == recipient, (
        f"the settlement named the wrong beneficiary: {settle[-1]['detail'].get('beneficiary_account_id')} "
        f"instead of the recipient {recipient}"
    )


def test_settlement_credential_is_not_persisted():
    """A deposit settlement issues a one-time settlement credential, and that credential is stripped
    before the settlement record reaches the on-disk audit log at /app/audit.log. An operator ingests a
    deposit and reconciles it to the finality depth; the resulting settlement record must be present yet
    carry neither the credential key nor a credential-like value. Because a deposit that is not applied is
    never settled, no settlement record is written until the deposit reaches the depth and is applied."""
    operator = login("erin")
    depth = relayer_status(operator)["finality_depth"]

    recipient = account_id("dave")
    height = 500300
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=4)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]

    reconcile(operator, height + depth)

    saw_settle = False
    for event in audit_records():
        if event.get("operation") != "relayer.settle":
            continue
        if event.get("target") == deposit_id:
            saw_settle = True
        detail = event.get("detail", {})
        assert "settlement_credential" not in all_keys(detail), (
            "a settlement record persisted the settlement credential key to the audit log"
        )
        for value in all_values(detail):
            assert not looks_like_credential(value), (
                f"a settlement record persisted a credential-like value to the audit log: {value}"
            )
    assert saw_settle, f"the settlement of {deposit_id} was not audited at all"


def test_confirmations_reported_are_exact():
    """The confirmation count reported for an applied deposit is exactly the number of L1 blocks built on
    top of it, `l1_tip - l1_height`. This accounting is correct and holds on both the buggy and the fixed
    node; it guards against a blanket edit that shifts the confirmation count while adjusting the finality
    boundary."""
    operator = login("erin")
    depth = relayer_status(operator)["finality_depth"]

    recipient = account_id("alice")
    height = 500400
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=2)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]

    tip = height + depth + 5
    outcome = reconcile(operator, tip)
    entry = [item for item in outcome["applied"] if item["id"] == deposit_id]
    assert entry, f"a deposit well past the depth was not applied: {outcome}"
    assert entry[0]["confirmations"] == tip - height, (
        f"confirmations were reported as {entry[0]['confirmations']}, expected {tip - height}"
    )


def test_settlement_records_the_ingesting_operator():
    """A settlement record attributes the deposit to the operator account that relayed it under a distinct
    field from the credited beneficiary. This attribution is correct and holds on both the buggy and the
    fixed node, so it fails if a blanket edit rewrites every operator reference in the settlement path into
    the recipient while correcting where the credit lands."""
    operator = login("erin")
    operator_id = account_id("erin")
    depth = relayer_status(operator)["finality_depth"]

    recipient = account_id("alice")
    height = 500500
    created = ingest_deposit(operator, l1_height=height, recipient=recipient, amount=5)
    assert created.status_code == 201, f"deposit ingest failed: {created.status_code} {created.text}"
    deposit_id = created.json()["id"]

    reconcile(operator, height + depth + 5)

    settle = [
        event
        for event in audit_records()
        if event.get("operation") == "relayer.settle" and event.get("target") == deposit_id
    ]
    assert settle, f"the settlement of {deposit_id} was not recorded"
    assert settle[-1]["detail"].get("ingested_by") == operator_id, (
        "the settlement record no longer attributes the relaying operator: "
        f"{settle[-1]['detail'].get('ingested_by')} instead of {operator_id}"
    )


def test_relayer_is_restricted_to_the_operator_role():
    """The relayer is an operator-plane surface, so a plain participant is refused deposit ingestion,
    reconciliation, and status while an operator is served. A participant that can read its own blocks
    must not thereby reach the L1 bridge."""
    participant = login("dave")
    recipient = account_id("dave")
    denied_ingest = ingest_deposit(participant, l1_height=42, recipient=recipient, amount=1)
    assert denied_ingest.status_code == 403, (
        f"a participant ingested an L1 deposit: {denied_ingest.status_code} {denied_ingest.text}"
    )
    denied_status = requests.get(f"{BASE}/v1/relayer/status", headers=auth(participant))
    assert denied_status.status_code == 403, "a participant read relayer status"
    denied_reconcile = requests.post(
        f"{BASE}/v1/relayer/reconcile", headers=auth(participant), json={"l1_tip": 10}
    )
    assert denied_reconcile.status_code == 403, "a participant reconciled the relayer"

    operator = login("erin")
    allowed = requests.get(f"{BASE}/v1/relayer/status", headers=auth(operator))
    assert allowed.status_code == 200, f"an operator was refused relayer status: {allowed.status_code}"
    assert allowed.json().get("network_id") == "network-alpha"


def test_duplicate_endorsements_do_not_double_count_toward_finality():
    """A block finalizes only when the combined stake of the distinct validators that have endorsed it
    reaches the two-thirds threshold, so a validator that endorses repeatedly contributes its weight only
    once. Alice registers three committee validators of stake 4, 3 and 2 (total 9, threshold 6) and has
    the stake-4 validator endorse the block twice; its distinct weight of 4 must leave the block below
    the threshold and unfinalized, with a distinct endorser count of one."""
    alice = login("alice")
    va = new_validator(alice, stake=4)
    vb = new_validator(alice, stake=3)
    vc = new_validator(alice, stake=2)

    created = create_block(alice, va, [va, vb, vc], height=10)
    assert created.status_code == 201, f"block create failed: {created.status_code} {created.text}"
    block_id = created.json()["id"]
    assert created.json()["total_power"] == 9
    assert created.json()["threshold_power"] == 6

    assert endorse_block(alice, block_id, va).status_code == 201
    second = endorse_block(alice, block_id, va)
    assert second.status_code == 201, f"a second endorsement was refused: {second.status_code} {second.text}"

    after = get_block(alice, block_id)
    assert after["endorsed_power"] == 4, (
        "a validator's repeated endorsement counted more than once toward finality: endorsed power was "
        f"{after['endorsed_power']}, expected 4"
    )
    assert after["finalized"] is False
    assert after["endorser_count"] == 1, f"a repeated endorsement inflated the distinct endorser count: {after}"


def test_distinct_endorsements_reach_the_threshold():
    """Finality tallying itself is correct: when distinct committee validators whose combined stake meets
    the two-thirds threshold endorse, the block finalizes with their combined weight."""
    alice = login("alice")
    va = new_validator(alice, stake=4)
    vb = new_validator(alice, stake=3)
    vc = new_validator(alice, stake=2)

    created = create_block(alice, va, [va, vb, vc], height=11)
    assert created.status_code == 201, f"block create failed: {created.status_code} {created.text}"
    block_id = created.json()["id"]

    assert endorse_block(alice, block_id, va).status_code == 201
    assert endorse_block(alice, block_id, vb).status_code == 201

    detail = get_block(alice, block_id)
    assert detail["endorsed_power"] == 7, f"two distinct endorsements should tally to 7: {detail}"
    assert detail["finalized"] is True, "a block with distinct endorsements over the threshold should finalize"
    assert detail["endorser_count"] == 2


def test_delegated_vote_lapses_when_delegator_loses_grant():
    """A re-delegated ballot lets its subject cast a governance vote only while the account that issued
    the delegation still holds its own ballot access. An owner issues carol a delegable grant, carol
    re-shares it to dave, and dave may vote while carol's grant stands. Once the owner revokes carol's
    grant, carol no longer holds the referendum, so dave's derived access lapses at once and a new vote
    by dave must be refused, while the owner votes throughout."""
    owner_j = _login_json("alice")
    owner = owner_j["token"]
    delegator_j = _login_json("carol")
    delegator, delegator_id = delegator_j["token"], delegator_j["account_id"]
    delegate_j = _login_json("dave")
    delegate, delegate_id = delegate_j["token"], delegate_j["account_id"]

    referendum_id = create_referendum(owner, f"r-{_S}-{uuid.uuid4().hex[:6]}", visibility="private")

    assert grant_ballot(owner, referendum_id, delegator_id, may_delegate=True).status_code == 201
    delegated = create_delegation(delegator, referendum_id, delegate_id)
    assert delegated.status_code == 201, f"delegation create failed: {delegated.status_code} {delegated.text}"

    assert cast_gov_vote(owner, referendum_id).status_code == 201, "owner refused its own referendum"
    assert cast_gov_vote(delegator, referendum_id).status_code == 201, "a direct grantee was refused"
    assert cast_gov_vote(delegate, referendum_id).status_code == 201, "a valid delegated vote was refused"

    revoked = revoke_ballot(owner, referendum_id, delegator_id)
    assert revoked.status_code == 200, f"grant revoke failed: {revoked.status_code} {revoked.text}"

    leaked = cast_gov_vote(delegate, referendum_id)
    assert leaked.status_code == 403, (
        "a delegated vote survived the account that issued it losing its own access to the referendum: "
        f"{leaked.status_code} {leaked.text}"
    )
    assert cast_gov_vote(delegator, referendum_id).status_code == 403, (
        "a direct grantee kept access after its grant was revoked"
    )


def test_delegation_listing_reflects_delegator_authority():
    """The delegation listing marks a re-shared ballot active only while the account that issued it
    still holds the referendum, so the same delegation flips from active to inactive once the
    delegator's grant is revoked. This is the read-side twin of the vote access rule and holds on both
    the buggy and the fixed node."""
    owner_j = _login_json("alice")
    owner = owner_j["token"]
    delegator_j = _login_json("carol")
    delegator, delegator_id = delegator_j["token"], delegator_j["account_id"]
    delegate_j = _login_json("dave")
    delegate_id = delegate_j["account_id"]

    referendum_id = create_referendum(owner, f"rl-{_S}-{uuid.uuid4().hex[:6]}", visibility="private")

    assert grant_ballot(owner, referendum_id, delegator_id, may_delegate=True).status_code == 201
    assert create_delegation(delegator, referendum_id, delegate_id).status_code == 201

    before = list_delegations(owner, referendum_id)
    mine = [d for d in before if d["subject_account_id"] == delegate_id]
    assert mine and mine[0]["active"] is True, f"a fresh delegation was not listed active: {before}"

    assert revoke_ballot(owner, referendum_id, delegator_id).status_code == 200

    after = list_delegations(owner, referendum_id)
    mine = [d for d in after if d["subject_account_id"] == delegate_id]
    assert mine and mine[0]["active"] is False, (
        f"a delegation stayed active after its delegator lost the referendum: {after}"
    )


def test_monitoring_stats_require_the_operator_role():
    """Operational node statistics are restricted to the operator or admin role, so a plain participant
    is refused the monitoring endpoint while an operator may read it. A participant that can view its own
    blocks must not thereby reach network-wide operational metrics."""
    participant = login("dave")
    denied = requests.get(f"{BASE}/v1/monitoring/stats", headers=auth(participant))
    assert denied.status_code == 403, (
        f"a plain participant read operational statistics: {denied.status_code} {denied.text}"
    )

    operator = login("erin")
    allowed = requests.get(f"{BASE}/v1/monitoring/stats", headers=auth(operator))
    assert allowed.status_code == 200, f"an operator was refused operational statistics: {allowed.status_code}"
    assert allowed.json().get("network_id") == "network-alpha"


def test_login_does_not_disclose_credential_validity():
    """A failed login does not reveal whether the account exists, so authenticating with an unknown
    username and authenticating a known account with the wrong password fail with the same status code
    and the same error code."""
    unknown = requests.post(
        f"{BASE}/v1/auth/token", json={"username": f"ghost-{_S}", "password": "whatever"}
    )
    bad_password = requests.post(
        f"{BASE}/v1/auth/token", json={"username": "alice", "password": "definitely-wrong"}
    )
    assert unknown.status_code == bad_password.status_code, (
        "login disclosed credential validity through the status code: "
        f"unknown-user {unknown.status_code} vs bad-password {bad_password.status_code}"
    )
    unknown_code = unknown.json().get("error", {}).get("code")
    bad_code = bad_password.json().get("error", {}).get("code")
    assert unknown_code == bad_code, (
        f"login disclosed credential validity through the error code: {unknown_code} vs {bad_code}"
    )
    assert unknown.status_code in (401, 403)


def test_unattested_validator_is_refused_at_activate():
    """A validator joins the active set only when its integrity attestation verifies, so activating a
    validator registered without an attestation is refused while an attested validator succeeds."""
    owner = login("alice")
    unattested = new_validator(owner, stake=3, attested=False, activate=False)
    weak = requests.post(f"{BASE}/v1/validators/{unattested}/activate", headers=auth(owner), json={})
    assert weak.status_code == 422, (
        f"a validator with no integrity attestation was activated: {weak.status_code} {weak.text}"
    )

    attested = new_validator(owner, stake=3, attested=True, activate=False)
    good = requests.post(f"{BASE}/v1/validators/{attested}/activate", headers=auth(owner), json={})
    assert good.status_code == 200, f"an attested validator was refused: {good.status_code} {good.text}"


def test_validator_detail_never_exposes_signing_key():
    """The validator detail endpoint reports validator state without exposing the validator signing key
    under any field name or as a credential-like value. This holds on both the buggy and the fixed node
    and guards the detail view against a change that surfaces server-side secrets."""
    owner = login("alice")
    validator = new_validator(owner, stake=2, attested=True, activate=False)

    detail = requests.get(f"{BASE}/v1/validators/{validator}", headers=auth(owner)).json()
    forbidden_keys = {"signing_key", "session_credential", "settlement_credential", "secret", "credential"}
    assert forbidden_keys.isdisjoint(all_keys(detail)), (
        f"validator detail exposed a secret key: {all_keys(detail)}"
    )
    for value in all_values(detail):
        assert not looks_like_credential(value), f"validator detail exposed a key-like value: {value}"


def test_activation_audit_excludes_session_credential():
    """A recorded validator activation is written to the on-disk audit log at /app/audit.log without
    persisting the issued session credential, so its stored records never carry that key or a
    credential-like value. This is correct on both the buggy and the fixed node and guards the audit
    storage path from a change that starts persisting activation secrets."""
    owner = login("alice")
    validator = new_validator(owner, stake=2, attested=True, activate=True)

    saw_activate = False
    for event in audit_records():
        if event.get("operation") == "validator.activate":
            saw_activate = True
        detail = event.get("detail", {})
        assert "session_credential" not in all_keys(detail), (
            "audit detail retained the session credential key"
        )
    assert saw_activate, f"the activation of {validator} was not audited at all"


def test_no_read_response_exposes_a_secret():
    """No read surface that should not carry secret material exposes a validator signing key, a session
    credential, or a settlement credential — neither under those field names nor as a credential-like
    value. Registration, activation, deposit settlement, a referendum and a block are exercised, then a
    broad set of detail, list, status, monitoring and audit-view responses is swept. The activation
    response, which mints and returns the one-time session credential, and the login token are excluded by
    design; every other route must stay clean."""
    operator = login("erin")
    owner = login("alice")
    depth = relayer_status(operator)["finality_depth"]

    registered = new_validator(owner, stake=2, attested=True, activate=False)
    active = new_validator(owner, stake=3, attested=True, activate=True)
    recipient = account_id("dave")
    deposit = ingest_deposit(operator, l1_height=510000, recipient=recipient, amount=5)
    assert deposit.status_code == 201, f"deposit ingest failed: {deposit.status_code} {deposit.text}"
    deposit_id = deposit.json()["id"]
    reconcile(operator, 510000 + depth)
    referendum_id = create_referendum(owner, f"sweep-{_S}-{uuid.uuid4().hex[:6]}")
    block = create_block(owner, active, [active], height=20)
    assert block.status_code == 201, f"block create failed: {block.status_code} {block.text}"
    block_id = block.json()["id"]

    responses = {
        "validator detail (registered)": requests.get(f"{BASE}/v1/validators/{registered}", headers=auth(owner)),
        "validator detail (active)": requests.get(f"{BASE}/v1/validators/{active}", headers=auth(owner)),
        "validator list": requests.get(f"{BASE}/v1/validators", headers=auth(owner)),
        "account": requests.get(f"{BASE}/v1/account", headers=auth(owner)),
        "deposit detail": requests.get(f"{BASE}/v1/relayer/deposits/{deposit_id}", headers=auth(operator)),
        "deposit list": requests.get(f"{BASE}/v1/relayer/deposits", headers=auth(operator)),
        "relayer status": requests.get(f"{BASE}/v1/relayer/status", headers=auth(operator)),
        "monitoring stats": requests.get(f"{BASE}/v1/monitoring/stats", headers=auth(operator)),
        "block detail": requests.get(f"{BASE}/v1/blocks/{block_id}", headers=auth(owner)),
        "referendum detail": requests.get(f"{BASE}/v1/referenda/{referendum_id}", headers=auth(owner)),
        "audit view": requests.get(f"{BASE}/v1/admin/audit?limit=200", headers=auth(operator)),
    }
    secret_keys = {"signing_key", "session_credential", "settlement_credential", "secret", "credential"}
    for label, resp in responses.items():
        assert resp.status_code == 200, f"{label} was not readable: {resp.status_code} {resp.text}"
        body = resp.json()
        assert secret_keys.isdisjoint(all_keys(body)), f"{label} exposed a secret key: {all_keys(body)}"
        for value in all_values(body):
            assert not looks_like_credential(value), f"{label} exposed a credential-like value: {value}"


def test_audit_log_persists_no_secret_across_event_types():
    """No audit event type persists secret material to /app/audit.log. Validator registration and
    activation, deposit ingestion and settlement, a governance action, and a failed login are exercised so
    a spread of operations reaches the log, then every stored record's detail is asserted free of the
    signing-key, session-credential, and settlement-credential keys and of any credential-like value,
    across all event types rather than a single operation."""
    operator = login("erin")
    owner = login("alice")
    depth = relayer_status(operator)["finality_depth"]

    new_validator(owner, stake=2, attested=True, activate=True)
    recipient = account_id("dave")
    deposit = ingest_deposit(operator, l1_height=520000, recipient=recipient, amount=5)
    assert deposit.status_code == 201, f"deposit ingest failed: {deposit.status_code} {deposit.text}"
    reconcile(operator, 520000 + depth)
    create_referendum(owner, f"audit-{_S}-{uuid.uuid4().hex[:6]}")
    requests.post(f"{BASE}/v1/auth/token", json={"username": f"nobody-{_S}", "password": "x"})

    secret_keys = {"signing_key", "session_credential", "settlement_credential"}
    seen_operations = set()
    for event in audit_records():
        seen_operations.add(event.get("operation"))
        detail = event.get("detail", {})
        assert secret_keys.isdisjoint(all_keys(detail)), (
            f"the {event.get('operation')} audit record persisted a secret key: {all_keys(detail)}"
        )
        for value in all_values(detail):
            assert not looks_like_credential(value), (
                f"the {event.get('operation')} audit record persisted a credential-like value: {value}"
            )
    for required in ("validator.register", "validator.activate"):
        assert required in seen_operations, f"expected {required} audit events were not produced"


def test_cross_network_validator_access_is_denied():
    """A validator is isolated to its owning network, so an account in a different network cannot read
    another network's validator detail even though its own role permits reading validators, while the
    owner still can."""
    owner = login("alice")
    validator = new_validator(owner, stake=2, attested=True, activate=False)

    owner_read = requests.get(f"{BASE}/v1/validators/{validator}", headers=auth(owner))
    assert owner_read.status_code == 200

    intruder = login("bob")
    other = requests.get(f"{BASE}/v1/validators/{validator}", headers=auth(intruder))
    assert other.status_code == 403, "a validator of another network was disclosed"


def test_validators_and_blocks_are_listed_for_their_network():
    """A freshly registered validator and a created block appear in their network's listings, confirming
    ordinary resource creation and network-scoped listing work end to end."""
    owner = login("alice")
    validator = new_validator(owner, stake=4, attested=True, activate=True)
    created = create_block(owner, validator, [validator], height=12)
    assert created.status_code == 201, f"block create failed: {created.status_code} {created.text}"
    block_id = created.json()["id"]

    validators = requests.get(f"{BASE}/v1/validators", headers=auth(owner)).json()["validators"]
    assert validator in [v["id"] for v in validators], "a freshly registered validator did not appear"

    blocks = requests.get(f"{BASE}/v1/blocks", headers=auth(owner)).json()["blocks"]
    assert block_id in [b["id"] for b in blocks], "a freshly created block did not appear"
