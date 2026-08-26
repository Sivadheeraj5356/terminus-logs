import json
import os
import re
import shutil
import subprocess
from datetime import datetime, timezone
from hashlib import sha256
from pathlib import Path

import pytest

BINARY = "/app/bin/commitment-chargeback"
APP_ROOT = Path("/app")
DATA_DIR = Path("/app/pledge_inputs")
CONTRACTS_DIR = Path("/app/billing_contracts")
OUTPUT_DIR = Path("/app/output")
OUTPUT_FILE = OUTPUT_DIR / "ledger.json"
SRC_DIR = Path("/app/carrydown_engine")

PLEDGE_INPUTS_BASELINE_FINGERPRINT = (
    "15130078576ccdacda05f5c5cf5ffbd8201211fe177cc2f2a3a1600db97a93ba"
)
BILLING_CONTRACTS_BASELINE_FINGERPRINT = (
    "f3f6dab9fd4886b5b16ffd50dd644fb15bdb326d284d9dd2d942fdb813702601"
)
LOCKED_ENGINE_HELPER_FINGERPRINT = (
    "923ea5dc96410db80bfa5fa12fb942bc02b049e93673d8126fb707bc58aef4fb"
)
LOCKED_ENGINE_HELPER_FILES = [
    "discount.go",
    "shared.go",
    "emit.go",
    "digest.go",
    "reconcile.go",
    "validate.go",
    "go.mod",
    "schema_hints.go",
    "config_flat.go",
    "digest_legacy.go",
    "ratecard_legacy.go",
    "tenant_row_v2.go",
    "ledger_export.go",
]
EXPECTED_REPORT_DIGEST = (
    "8465de14141726bbcffc91c5ab826319b5a1f443bb7010a948ef0745453ba0ad"
)
WRONG_ALPHA_SORT_DIGEST = (
    "a972d76f42dc5e313f94f48728cc0f69fd1ec7be15d11b8ebfd8937201674d27"
)
EXPECTED_DIGEST_PAYLOAD_LEN_BYTES = 179
EXPECTED_DIGEST_ROWS = [
    "tn-arc|1132185|514900|617285",
    "tn-cir|523325|238000|285325",
    "tn-bor|501453|277500|223953",
    "tn-delt|353999|195900|158099",
    "tn-pivot|100100|100100|0",
    "tn-flux|28145|12800|15345",
    "tn-echo|0|0|0",
]
EXPECTED_SHARED_POOL_SHARES = {
    "tn-arc": 617285,
    "tn-cir": 285325,
    "tn-bor": 223953,
    "tn-delt": 158099,
    "tn-pivot": 0,
    "tn-flux": 15345,
    "tn-echo": 0,
}
EXPECTED_SUMMARY = {
    "tenant_count": 7,
    "total_billable_microcents": 2639207,
    "pool_total_microcents": 1300007,
    "pool_unallocated_microcents": 0,
    "credit_applied_microcents": 130000,
    "commitment_discount_microcents": 160500,
}
ACTIVE_TENANT_IDS = {
    "tn-arc",
    "tn-bor",
    "tn-cir",
    "tn-delt",
    "tn-echo",
    "tn-flux",
    "tn-pivot",
}

ROOT_KEYS = [
    "period_id",
    "currency",
    "tenants",
    "summary",
    "report_digest",
]
TENANT_KEYS = [
    "tenant_id",
    "name",
    "line_items",
    "subtotal_microcents",
    "credit_applied_microcents",
    "commitment_discount_microcents",
    "net_usage_microcents",
    "shared_allocated_microcents",
    "total_charge_microcents",
]
LINE_ITEM_KEYS = [
    "service",
    "units",
    "list_cost_microcents",
    "committed_units",
    "committed_discount_microcents",
    "on_demand_units",
    "on_demand_cost_microcents",
]
SUMMARY_KEYS = [
    "tenant_count",
    "total_billable_microcents",
    "pool_total_microcents",
    "pool_unallocated_microcents",
    "credit_applied_microcents",
    "commitment_discount_microcents",
]

USAGE_FILES = [
    "usage_compute_01.ndjson",
    "usage_compute_02.ndjson",
    "usage_compute_03.ndjson",
    "usage_compute_04.ndjson",
    "usage_storage_01.ndjson",
    "usage_storage_02.ndjson",
    "usage_egress_01.ndjson",
    "usage_egress_02.ndjson",
    "usage_carrydown_tie.ndjson",
    "usage_out_of_period.ndjson",
    "usage_inactive_tenant.ndjson",
    "usage_micro_burst.ndjson",
    "usage_seam_probe.ndjson",
    "usage_credit_stress.ndjson",
]
SCOPE_RANK = {"global": 1, "region": 2, "tenant": 3}


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def load_ndjson_path(path):
    rows = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def resolve_rate(rates, service, tenant_id, region, ts):
    best = None
    for rc in rates:
        if rc["service"] != service:
            continue
        if not (parse_ts(rc["effective_from"]) <= ts < parse_ts(rc["effective_until"])):
            continue
        scope = rc["scope"]
        if scope == "region" and rc["scope_key"] != region:
            continue
        if scope == "tenant" and rc["scope_key"] != tenant_id:
            continue
        if scope not in SCOPE_RANK:
            continue
        if best is None or SCOPE_RANK[scope] > SCOPE_RANK[best["scope"]]:
            best = rc
    if best is None:
        raise AssertionError("no active rate for %s %s" % (service, tenant_id))
    return best["unit_rate_microcents"]


def allocate_pool(total, participants, weights, tie_break="tenant_id_asc"):
    eff = {p: max(weights.get(p, 0), 0) for p in participants}
    wsum = sum(eff.values())
    if wsum == 0:
        eff = {p: 1 for p in participants}
        wsum = len(participants)
    floors = {}
    remainders = {}
    for p in participants:
        numerator = total * eff[p]
        floors[p] = numerator // wsum
        remainders[p] = numerator - floors[p] * wsum
    leftover = total - sum(floors.values())
    if tie_break == "tenant_id_asc":
        order = sorted(participants, key=lambda p: (-remainders[p], p))
    else:
        raise AssertionError("unsupported remainder_tie_break %s" % tie_break)
    for i in range(leftover):
        floors[order[i]] += 1
    return floors


def load_config(data_dir=None):
    data_dir = data_dir or DATA_DIR
    return json.loads((Path(data_dir) / "config.json").read_text(encoding="utf-8"))


def active_tenant_count(data_dir=None):
    data_dir = Path(data_dir or DATA_DIR)
    tenants = json.loads((data_dir / "tenants.json").read_text(encoding="utf-8"))["tenants"]
    return sum(1 for t in tenants if t.get("active", True))


def pool_total_for_period(data_dir=None):
    data_dir = Path(data_dir or DATA_DIR)
    cfg = load_config(data_dir)
    period_id = cfg["billing_period"]["period_id"]
    pools = json.loads((data_dir / "shared_pools.json").read_text(encoding="utf-8"))["pools"]
    return sum(p["total_cost_microcents"] for p in pools if p["period_id"] == period_id)


def sort_tenants_by_config(rows, cfg):
    """Reorder tenant rows using ledger_sort tokens from config.json."""
    sort_keys = []
    for token in cfg["ledger_sort"]:
        if token == "total_charge_microcents_desc":
            sort_keys.append(lambda r, _t=token: -r["total_charge_microcents"])
        elif token == "tenant_id_asc":
            sort_keys.append(lambda r, _t=token: r["tenant_id"])
        else:
            raise AssertionError("unsupported ledger_sort token %s" % token)
    return sorted(rows, key=lambda r: tuple(k(r) for k in sort_keys))


def apply_discounts(subtotal, credit_avail, commit_raw, precedence):
    """Apply reductions in config precedence order against a running balance."""
    running = subtotal
    credit_applied = 0
    commitment_applied = 0
    for step in precedence:
        if step == "credit":
            credit_applied = min(credit_avail, running)
            running -= credit_applied
        elif step == "commitment":
            commitment_applied = min(commit_raw, running)
            running -= commitment_applied
        elif step == "on_demand":
            continue
        else:
            raise AssertionError("unsupported precedence step %s" % step)
    return credit_applied, commitment_applied, running


def compute_ledger(data_dir):
    data_dir = str(data_dir)
    cfg = json.load(open(os.path.join(data_dir, "config.json")))
    tenants = json.load(open(os.path.join(data_dir, "tenants.json")))["tenants"]
    rates = load_ndjson_path(os.path.join(data_dir, "rate_cards.ndjson"))
    commitments = load_ndjson_path(os.path.join(data_dir, "commitments.ndjson"))
    credits = load_ndjson_path(os.path.join(data_dir, "credits.ndjson"))
    pools = json.load(open(os.path.join(data_dir, "shared_pools.json")))["pools"]
    events = []
    for fn in USAGE_FILES:
        events.extend(load_ndjson_path(os.path.join(data_dir, fn)))

    period = cfg["billing_period"]
    p_start = parse_ts(period["start_inclusive"])
    p_end = parse_ts(period["end_exclusive"])
    period_id = period["period_id"]
    services = cfg["line_item_order"]
    region = {t["tenant_id"]: t["region"] for t in tenants}
    name = {t["tenant_id"]: t["name"] for t in tenants}

    active = {t["tenant_id"] for t in tenants if t.get("active", True)}
    in_period = [
        e
        for e in events
        if p_start <= parse_ts(e["timestamp"]) < p_end and e["tenant_id"] in active
    ]

    commit_map = {}
    for c in commitments:
        if c["period_id"] == period_id:
            commit_map[(c["tenant_id"], c["service"])] = c
    credit_map = {}
    for cr in credits:
        if cr["period_id"] == period_id:
            credit_map[cr["tenant_id"]] = credit_map.get(cr["tenant_id"], 0) + cr["amount_microcents"]

    def service_line(tid, svc):
        evs = [e for e in in_period if e["tenant_id"] == tid and e["service"] == svc]
        evs.sort(key=lambda e: (parse_ts(e["timestamp"]), e["event_id"]))
        commit = commit_map.get((tid, svc))
        remaining = commit["committed_units"] if commit else 0
        disc = commit["discount_rate_microcents"] if commit else 0
        agg = {
            "total_units": 0,
            "list_cost": 0,
            "committed_units": 0,
            "committed_discount": 0,
            "on_demand_units": 0,
            "on_demand_cost": 0,
        }
        for e in evs:
            rate = resolve_rate(rates, svc, tid, region[tid], parse_ts(e["timestamp"]))
            units = e["units"]
            agg["total_units"] += units
            agg["list_cost"] += units * rate
            committed = min(units, remaining)
            remaining -= committed
            agg["committed_units"] += committed
            agg["committed_discount"] += committed * (rate - disc)
            on_demand = units - committed
            agg["on_demand_units"] += on_demand
            agg["on_demand_cost"] += on_demand * rate
        return agg

    net_by = {}
    pre = {}
    for t in tenants:
        tid = t["tenant_id"]
        if tid not in active:
            continue
        line_items = []
        subtotal = 0
        commit_raw = 0
        for svc in services:
            agg = service_line(tid, svc)
            subtotal += agg["list_cost"]
            commit_raw += agg["committed_discount"]
            if agg["total_units"] > 0:
                line_items.append({
                    "service": svc,
                    "units": agg["total_units"],
                    "list_cost_microcents": agg["list_cost"],
                    "committed_units": agg["committed_units"],
                    "committed_discount_microcents": agg["committed_discount"],
                    "on_demand_units": agg["on_demand_units"],
                    "on_demand_cost_microcents": agg["on_demand_cost"],
                })
        credit_applied, commitment_applied, net = apply_discounts(
            subtotal,
            credit_map.get(tid, 0),
            commit_raw,
            cfg["precedence"],
        )
        net_by[tid] = net
        pre[tid] = {
            "name": name[tid],
            "line_items": line_items,
            "subtotal": subtotal,
            "credit_applied": credit_applied,
            "commitment_discount": commitment_applied,
            "net": net,
        }

    shared_by = {tid: 0 for tid in active}
    for pool in pools:
        if pool["period_id"] != period_id:
            continue
        parts = pool["participants"]
        weights = {p: net_by.get(p, 0) for p in parts}
        alloc = allocate_pool(
            pool["total_cost_microcents"],
            parts,
            weights,
            tie_break=cfg.get("remainder_tie_break", "tenant_id_asc"),
        )
        for p in parts:
            shared_by[p] += alloc[p]

    rows = []
    sum_credit = 0
    sum_commit = 0
    for t in tenants:
        tid = t["tenant_id"]
        if tid not in active:
            continue
        pr = pre[tid]
        shared = shared_by[tid]
        total = pr["net"] + shared
        sum_credit += pr["credit_applied"]
        sum_commit += pr["commitment_discount"]
        rows.append({
            "tenant_id": tid,
            "name": pr["name"],
            "line_items": pr["line_items"],
            "subtotal_microcents": pr["subtotal"],
            "credit_applied_microcents": pr["credit_applied"],
            "commitment_discount_microcents": pr["commitment_discount"],
            "net_usage_microcents": pr["net"],
            "shared_allocated_microcents": shared,
            "total_charge_microcents": total,
        })
    rows = sort_tenants_by_config(rows, cfg)

    pool_total = sum(p["total_cost_microcents"] for p in pools if p["period_id"] == period_id)
    total_billable = sum(x["total_charge_microcents"] for x in rows)
    summary = {
        "tenant_count": len(rows),
        "total_billable_microcents": total_billable,
        "pool_total_microcents": pool_total,
        "pool_unallocated_microcents": 0,
        "credit_applied_microcents": sum_credit,
        "commitment_discount_microcents": sum_commit,
    }

    blob = "".join(
        "%s|%d|%d|%d\n" % (
            x["tenant_id"],
            x["total_charge_microcents"],
            x["net_usage_microcents"],
            x["shared_allocated_microcents"],
        )
        for x in rows
    )
    digest = sha256(blob.encode("utf-8")).hexdigest()

    return {
        "period_id": period_id,
        "currency": cfg["currency"],
        "tenants": rows,
        "summary": summary,
        "report_digest": digest,
    }


def hash_tree(root):
    entries = {}
    for dirpath, _dirnames, filenames in os.walk(root):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, root)
            with open(full, "rb") as f:
                entries[rel] = sha256(f.read()).hexdigest()
    return entries


def tree_fingerprint(root):
    h = sha256()
    entries = hash_tree(root)
    for rel in sorted(entries):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        h.update(entries[rel].encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def locked_engine_helper_fingerprint():
    h = sha256()
    for name in sorted(LOCKED_ENGINE_HELPER_FILES):
        body = (SRC_DIR / name).read_bytes()
        h.update(name.encode("utf-8"))
        h.update(b"\0")
        h.update(sha256(body).hexdigest().encode("utf-8"))
        h.update(b"\0")
    return h.hexdigest()


def rebuild_from_carrydown_engine():
    env = os.environ.copy()
    env["PATH"] = "/usr/local/go/bin:/go/bin:" + env.get("PATH", "")
    subprocess.run(
        ["go", "build", "-o", BINARY, "."],
        cwd=str(SRC_DIR),
        check=True,
        env=env,
    )


def run_binary():
    subprocess.run([BINARY], check=True)


def load_output():
    return json.loads(OUTPUT_FILE.read_text())


@pytest.fixture(scope="module", autouse=True)
def rebuild_binary():
    assert tree_fingerprint(DATA_DIR) == PLEDGE_INPUTS_BASELINE_FINGERPRINT
    assert tree_fingerprint(CONTRACTS_DIR) == BILLING_CONTRACTS_BASELINE_FINGERPRINT
    rebuild_from_carrydown_engine()


@pytest.fixture(scope="module")
def ledger():
    run_binary()
    return load_output()


@pytest.fixture(scope="module")
def expected():
    return compute_ledger(DATA_DIR)


def find_tenant(rows, tenant_id):
    for row in rows:
        if row["tenant_id"] == tenant_id:
            return row
    raise AssertionError("tenant %s missing" % tenant_id)


def find_line_item(row, service):
    for li in row["line_items"]:
        if li["service"] == service:
            return li
    return None


def digest_blob_for_tenants(tenants):
    return "".join(
        "%s|%d|%d|%d\n" % (
            row["tenant_id"],
            row["total_charge_microcents"],
            row["net_usage_microcents"],
            row["shared_allocated_microcents"],
        )
        for row in tenants
    ).encode("utf-8")


def tenant_raw_chunk(raw, tenant_id):
    marker = '"tenant_id": "%s"' % tenant_id
    start = raw.index(marker)
    next_idx = raw.find('"tenant_id":', start + len(marker))
    if next_idx == -1:
        return raw[start:]
    return raw[start:next_idx]


def assert_json_keys_in_order(chunk, keys):
    cursor = 0
    positions = []
    for key in keys:
        pos = chunk.index('"%s"' % key, cursor)
        positions.append(pos)
        cursor = pos + 1
    assert positions == sorted(positions)


def test_writes_only_touch_output_ledger():
    """SCHEMA.md / anti-cheat: a run may change only /app/output/ledger.json under /app."""
    before = hash_tree(APP_ROOT)
    run_binary()
    after = hash_tree(APP_ROOT)
    changed = sorted(
        rel for rel in set(before) | set(after) if before.get(rel) != after.get(rel)
    )
    assert set(changed) <= {"output/ledger.json"}
    assert str(OUTPUT_DIR) == "/app/output"
    assert sorted(entry.name for entry in OUTPUT_DIR.iterdir()) == ["ledger.json"]


def test_full_ledger_equals_reference(ledger, expected):
    """SCHEMA.md: whole ledger equals independent recomputation from contract rules."""
    assert ledger == expected


def test_ledger_output_schema_contract(ledger):
    """SCHEMA.md: key order, banned fields, line_item_order, pretty JSON integers, no nulls."""
    assert list(ledger.keys()) == ROOT_KEYS
    for banned_root in (
        "schema_version",
        "ledger_sort",
        "precedence",
        "billing_period",
        "micro_cents_per_usd",
        "line_item_order",
        "format_version",
        "reserved",
    ):
        assert banned_root not in ledger
    cfg = load_config()
    service_order = cfg["line_item_order"]
    for row in ledger["tenants"]:
        assert list(row.keys()) == TENANT_KEYS
        for extra in ("region", "active", "period_id", "currency"):
            assert extra not in row
        assert isinstance(row["line_items"], list)
        services = [li["service"] for li in row["line_items"]]
        assert services == [s for s in service_order if s in services]
        for li in row["line_items"]:
            assert list(li.keys()) == LINE_ITEM_KEYS
            assert li["units"] > 0
    assert list(ledger["summary"].keys()) == SUMMARY_KEYS
    raw = OUTPUT_FILE.read_text(encoding="utf-8")
    assert raw.endswith("\n") and not raw.endswith("\n\n")
    assert any(line.startswith("  ") for line in raw.splitlines())
    assert '": ' in raw
    assert "null" not in raw
    assert '"schema_version"' not in raw and '"format_version"' not in raw
    for match in re.finditer(r'"[^"]*microcents":\s*([^,\}\]\n]+)', raw):
        assert re.fullmatch(r"-?\d+", match.group(1).strip())
    assert_json_keys_in_order(raw, ROOT_KEYS)
    arc_chunk = tenant_raw_chunk(raw, "tn-arc")
    assert_json_keys_in_order(arc_chunk, TENANT_KEYS)


def test_carrydown_required_files_exist_stdlib_build():
    """instruction.md: keep listed Go files separate; stdlib go build emits ELF at /app/bin/commitment-chargeback."""
    for name in (
        "emit.go",
        "digest.go",
        "reconcile.go",
        "validate.go",
        "commitment.go",
        "discount.go",
        "intake.go",
        "main.go",
        "ratecard.go",
        "shared.go",
    ):
        assert (SRC_DIR / name).is_file(), name
    main = (SRC_DIR / "main.go").read_text(encoding="utf-8")
    assert '"/app/pledge_inputs"' in main and '"/app/output"' in main
    rebuild_from_carrydown_engine()
    binary = Path(BINARY)
    assert binary.is_file() and not binary.is_symlink()
    assert binary.read_bytes()[:4] == b"\x7fELF"


def test_locked_engine_helpers_byte_identical_to_image():
    """SCHEMA.md: only commitment.go ratecard.go intake.go main.go may change; helpers stay baseline."""
    assert locked_engine_helper_fingerprint() == LOCKED_ENGINE_HELPER_FINGERPRINT


def test_event_id_tie_break_orders_cir_carrydown(ledger, expected):
    """SCHEMA.md: timestamp then event_id ascending encounter order drives commitment burn."""
    row = find_tenant(ledger["tenants"], "tn-cir")
    li = find_line_item(row, "compute")
    assert li == find_line_item(find_tenant(expected["tenants"], "tn-cir"), "compute")
    assert li["units"] == 70
    assert li["committed_units"] == 40
    assert li["on_demand_units"] == 30
    assert li["committed_discount_microcents"] == 32000
    # reversed event_id order at equal timestamp would rearrange pledged units on the tie shard
    assert li["committed_units"] != 43


def test_flux_micro_burst_commitment_carrydown_caps_at_pledge_four_units(ledger, expected):
    """SCHEMA.md: stateful pledge decrement caps micro-burst usage at committed_units."""
    flux = find_tenant(ledger["tenants"], "tn-flux")
    li = find_line_item(flux, "compute")
    assert li == find_line_item(find_tenant(expected["tenants"], "tn-flux"), "compute")
    assert li["units"] == 5 and li["committed_units"] == 4 and li["on_demand_units"] == 1
    assert li["committed_discount_microcents"] == 12000
    assert flux["credit_applied_microcents"] == 15000
    assert flux["total_charge_microcents"] == 28145


def test_delt_compute_only_line_item_omits_zero_unit_egress_commitment(ledger, expected):
    """SCHEMA.md: omit zero-unit services even when an unused egress commitment exists."""
    delt = find_tenant(ledger["tenants"], "tn-delt")
    assert delt == find_tenant(expected["tenants"], "tn-delt")
    assert [li["service"] for li in delt["line_items"]] == ["compute"]
    assert find_line_item(delt, "egress") is None
    assert delt["total_charge_microcents"] == 353999
    assert delt["shared_allocated_microcents"] == 158099


def test_digest_payload_len_bytes_exact(ledger, expected):
    """SCHEMA.md: digest utf8 pipe payload length matches ledger-order tenant rows."""
    blob = digest_blob_for_tenants(ledger["tenants"])
    assert len(blob) == EXPECTED_DIGEST_PAYLOAD_LEN_BYTES
    assert blob.decode("utf-8").split("\n")[:-1] == EXPECTED_DIGEST_ROWS
    assert sha256(blob).hexdigest() == EXPECTED_REPORT_DIGEST == ledger["report_digest"]


def test_digest_truncated_tail_rejects_checksum(ledger):
    """SCHEMA.md: digest rejects truncated_tail, partial, payload_plus, buffer-cap, dup_seq, swapped fields."""
    blob = digest_blob_for_tenants(ledger["tenants"])
    assert sha256(blob).hexdigest() == ledger["report_digest"] == EXPECTED_REPORT_DIGEST
    assert sha256(blob[:-1]).hexdigest() != ledger["report_digest"]
    assert sha256(blob[: len(blob) // 2]).hexdigest() != ledger["report_digest"]
    assert sha256(blob + b"x").hexdigest() != ledger["report_digest"]
    assert sha256(blob[:32]).hexdigest() != ledger["report_digest"]
    swapped = "".join(
        "%s|%d|%d|%d\n"
        % (
            row["tenant_id"],
            row["net_usage_microcents"],
            row["total_charge_microcents"],
            row["shared_allocated_microcents"],
        )
        for row in ledger["tenants"]
    ).encode("utf-8")
    assert sha256(swapped).hexdigest() != ledger["report_digest"]
    dup_seq = blob + blob.split(b"\n")[-2] + b"\n"
    assert sha256(dup_seq).hexdigest() != ledger["report_digest"]
    extra = "".join(
        "%s|%d|%d|%d|0\n"
        % (
            row["tenant_id"],
            row["total_charge_microcents"],
            row["net_usage_microcents"],
            row["shared_allocated_microcents"],
        )
        for row in ledger["tenants"]
    ).encode("utf-8")
    assert sha256(extra).hexdigest() != ledger["report_digest"]


def test_pool_allocates_net_weights_not_subtotal(ledger, expected):
    """SCHEMA.md: pool weights use net after precedence not list subtotal; largest remainder exact shares."""
    assert ledger["summary"]["pool_unallocated_microcents"] == 0
    for tenant_id, shared in EXPECTED_SHARED_POOL_SHARES.items():
        row = find_tenant(ledger["tenants"], tenant_id)
        assert row["shared_allocated_microcents"] == shared
        assert row["total_charge_microcents"] == (
            row["net_usage_microcents"] + row["shared_allocated_microcents"]
        )
    arc = find_tenant(ledger["tenants"], "tn-arc")
    # subtotal-weighted pool allocation diverges from net-weighted golden shares
    assert arc["shared_allocated_microcents"] == 617285
    assert arc["subtotal_microcents"] != arc["net_usage_microcents"]
    assert arc == find_tenant(expected["tenants"], "tn-arc")


def test_summary_rollups_exact_totals(ledger, expected):
    """SCHEMA.md: summary rollups conserve pool, credit, and commitment totals."""
    assert ledger["summary"] == EXPECTED_SUMMARY == expected["summary"]


def test_intake_loads_all_manifest_shards_including_credit_stress(ledger):
    """SCHEMA.md: load every manifest shard; embed each shard filename (not contents) as a Go string literal."""
    manifest = json.loads((DATA_DIR / "usage_shards.json").read_text(encoding="utf-8"))
    assert manifest["usage_shard_files"] == USAGE_FILES
    sources = "\n".join(p.read_text(encoding="utf-8") for p in sorted(SRC_DIR.rglob("*.go")))
    assert "usage_shards.json" in sources
    for fn in USAGE_FILES:
        assert '"%s"' % fn in sources, fn
    arc = find_tenant(ledger["tenants"], "tn-arc")
    assert arc["credit_applied_microcents"] == 90000


def test_arc_committed_units_cap_at_pledge_not_per_event_reset(ledger, expected):
    """SCHEMA.md: one running remaining balance; discount uses each event's resolved unit rate minus discount rate."""
    arc = find_tenant(ledger["tenants"], "tn-arc")
    compute = find_line_item(arc, "compute")
    assert compute == find_line_item(find_tenant(expected["tenants"], "tn-arc"), "compute")
    assert compute["committed_units"] == 100
    assert compute["committed_discount_microcents"] == 92500
    assert compute["on_demand_units"] == 72


def test_cir_compute_rejects_lexicographic_rc_aaa_cheaper_rate(ledger, expected):
    """SCHEMA.md: same-scope first file match; reject lexicographic rc-aaa-cheaper 3900."""
    cir = find_tenant(ledger["tenants"], "tn-cir")
    li = find_line_item(cir, "compute")
    assert li == find_line_item(find_tenant(expected["tenants"], "tn-cir"), "compute")
    assert li["list_cost_microcents"] == 280000
    assert li["list_cost_microcents"] != 70 * 3900
    assert cir["total_charge_microcents"] == 523325


def test_arc_credit_stress_dual_pool_exact_shares(ledger, expected):
    """SCHEMA.md: credit-before-commitment precedence and dual-pool shares for tn-arc."""
    arc = find_tenant(ledger["tenants"], "tn-arc")
    assert arc == find_tenant(expected["tenants"], "tn-arc")
    assert ledger["tenants"][0]["tenant_id"] == "tn-arc"
    assert arc["credit_applied_microcents"] == 90000
    assert arc["commitment_discount_microcents"] == 92500
    assert arc["net_usage_microcents"] == 514900
    assert arc["shared_allocated_microcents"] == 617285
    assert arc["total_charge_microcents"] == 1132185


def test_active_tenant_roster_includes_zero_usage_echo(ledger, expected):
    """SCHEMA.md: every active tenant including zero-usage echo; omit inactive muted."""
    tenant_ids = {row["tenant_id"] for row in ledger["tenants"]}
    assert tenant_ids == ACTIVE_TENANT_IDS
    assert "tn-muted" not in tenant_ids
    row = find_tenant(ledger["tenants"], "tn-echo")
    assert row == find_tenant(expected["tenants"], "tn-echo")
    assert row["line_items"] == []
    assert row["total_charge_microcents"] == 0


def test_rate_seam_half_open_window_on_tn_bor_compute(ledger, expected):
    """SCHEMA.md: half-open rate windows on tn-bor seam; reject last-wins global 4500."""
    row = find_tenant(ledger["tenants"], "tn-bor")
    li = find_line_item(row, "compute")
    assert li["list_cost_microcents"] == 277500
    assert li["list_cost_microcents"] != 64 * 4500
    assert row["total_charge_microcents"] == 501453
    assert row["shared_allocated_microcents"] == 223953


def test_arc_compute_list_cost_rejects_wrong_rate_scope_tie(ledger, expected):
    """SCHEMA.md: tenant scope beats region/global for tn-arc compute list cost."""
    arc = find_tenant(ledger["tenants"], "tn-arc")
    li = find_line_item(arc, "compute")
    assert li["list_cost_microcents"] == 658900
    assert li["list_cost_microcents"] != li["units"] * 4000
    assert li["list_cost_microcents"] != li["units"] * 4200
    assert arc["total_charge_microcents"] == 1132185


def test_us_east_region_first_match_rejects_later_same_scope_card(ledger, expected):
    """SCHEMA.md: overlapping us-east region cards keep first file match across tenants."""
    for tid, units, list_cost in (
        ("tn-cir", 70, 280000),
        ("tn-flux", 5, 20000),
        ("tn-pivot", 24, 96000),
    ):
        li = find_line_item(find_tenant(ledger["tenants"], tid), "compute")
        assert li["units"] == units
        assert li["list_cost_microcents"] == list_cost
        assert li["list_cost_microcents"] != units * 3900


def test_digest_rejects_alpha_sorted_tenant_payload_checksum(ledger):
    """SCHEMA.md: report_digest uses ledger order not tenant_id alphabetical order."""
    alpha = sorted(ledger["tenants"], key=lambda row: row["tenant_id"])
    alpha_digest = sha256(digest_blob_for_tenants(alpha)).hexdigest()
    assert alpha_digest == WRONG_ALPHA_SORT_DIGEST
    assert ledger["report_digest"] == EXPECTED_REPORT_DIGEST
    assert ledger["report_digest"] != alpha_digest


def test_digest_ledger_tenant_array_order_rejects_alpha_and_roster(ledger):
    """SCHEMA.md: digest row order matches ledger tenants not roster file order."""
    tenant_ids = [row["tenant_id"] for row in ledger["tenants"]]
    assert tenant_ids == [line.split("|")[0] for line in EXPECTED_DIGEST_ROWS]
    roster_ids = [
        t["tenant_id"]
        for t in json.loads((DATA_DIR / "tenants.json").read_text(encoding="utf-8"))["tenants"]
        if t.get("active", True)
    ]
    assert tenant_ids != sorted(ACTIVE_TENANT_IDS)
    assert tenant_ids != roster_ids


def test_report_digest_sha256_compact_pipe_rows_in_ledger_sort_order(ledger, expected):
    """SCHEMA.md: lowercase sha256 over pipe rows in ledger sort order."""
    digest = ledger["report_digest"]
    assert digest == expected["report_digest"] == EXPECTED_REPORT_DIGEST
    assert re.fullmatch(r"[0-9a-f]{64}", digest)
    blob = digest_blob_for_tenants(ledger["tenants"])
    assert sha256(blob).hexdigest() == digest
    assert blob.endswith(b"\n") and not blob.endswith(b"\n\n")


def test_byte_identical_fresh_build_delete_output_three_reruns(ledger):
    """SCHEMA.md / instruction.md: fresh builds and three reruns are byte-identical."""
    rebuild_from_carrydown_engine()
    run_binary()
    first = OUTPUT_FILE.read_bytes()
    for _ in range(3):
        run_binary()
        assert OUTPUT_FILE.read_bytes() == first
    shutil.rmtree(OUTPUT_DIR)
    OUTPUT_DIR.mkdir(parents=True)
    run_binary()
    assert OUTPUT_FILE.read_bytes() == first
    assert json.loads(first.decode("utf-8")) == ledger


def test_runtime_zero_weight_pool_swap_missing_active_defaults_true(ledger):
    """SCHEMA.md: runtime swap covers missing active defaults true and all-zero pool fallback."""
    tenants_path = DATA_DIR / "tenants.json"
    pools_path = DATA_DIR / "shared_pools.json"
    backups = {
        tenants_path: (tenants_path.read_bytes(), tenants_path.stat().st_mode),
        pools_path: (pools_path.read_bytes(), pools_path.stat().st_mode),
    }
    try:
        tenants_doc = json.loads(tenants_path.read_text(encoding="utf-8"))
        tenants_doc["tenants"].append({
            "tenant_id": "tn-runtime",
            "name": "Runtime Zero",
            "region": "us-east",
        })
        pools_doc = json.loads(pools_path.read_text(encoding="utf-8"))
        pools_doc["pools"].append({
            "pool_id": "sp-runtime-zero",
            "period_id": "2027-03",
            "total_cost_microcents": 7,
            "participants": ["tn-echo", "tn-runtime"],
        })
        for path, (_body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
        tenants_path.write_text(json.dumps(tenants_doc, indent=2) + "\n", encoding="utf-8")
        pools_path.write_text(json.dumps(pools_doc, indent=2) + "\n", encoding="utf-8")

        run_binary()
        swapped = load_output()
        expected = compute_ledger(DATA_DIR)
        assert swapped == expected
        runtime = find_tenant(swapped["tenants"], "tn-runtime")
        echo = find_tenant(swapped["tenants"], "tn-echo")
        assert runtime["line_items"] == []
        assert runtime["shared_allocated_microcents"] == 3
        assert runtime["total_charge_microcents"] == 3
        assert echo["shared_allocated_microcents"] == 4
        assert swapped["summary"]["tenant_count"] == 8
        assert swapped["summary"]["pool_total_microcents"] == 1300014
    finally:
        for path, (body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
            path.write_bytes(body)
            os.chmod(path, mode)
        run_binary()


def test_runtime_precedence_swap_credit_cap_uses_config_order(ledger):
    """SCHEMA.md: read precedence from config.json each run (not hardcoded); credit caps at remaining balance."""
    config_path = DATA_DIR / "config.json"
    credits_path = DATA_DIR / "credits.ndjson"
    backups = {
        config_path: (config_path.read_bytes(), config_path.stat().st_mode),
        credits_path: (credits_path.read_bytes(), credits_path.stat().st_mode),
    }
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg["precedence"] = ["commitment", "credit", "on_demand"]
        for path, (_body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
        config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        with credits_path.open("a", encoding="utf-8") as f:
            f.write(
                '{"credit_id": "cr-runtime-arc-big", "tenant_id": "tn-arc", '
                '"period_id": "2027-03", "amount_microcents": 650000}\n'
            )

        run_binary()
        swapped = load_output()
        expected = compute_ledger(DATA_DIR)
        assert swapped == expected
        arc = find_tenant(swapped["tenants"], "tn-arc")
        assert arc["commitment_discount_microcents"] == 92500
        assert arc["credit_applied_microcents"] == 604900
        assert arc["net_usage_microcents"] == 0
        assert swapped["summary"]["credit_applied_microcents"] == 644900
        assert swapped["summary"]["commitment_discount_microcents"] == 160500
    finally:
        for path, (body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
            path.write_bytes(body)
            os.chmod(path, mode)
        run_binary()


def test_runtime_remainder_tie_break_tenant_id_asc(ledger):
    """SCHEMA.md: largest-remainder leftover ties break by tenant_id ascending, not descending."""
    tenants_path = DATA_DIR / "tenants.json"
    pools_path = DATA_DIR / "shared_pools.json"
    backups = {
        tenants_path: (tenants_path.read_bytes(), tenants_path.stat().st_mode),
        pools_path: (pools_path.read_bytes(), pools_path.stat().st_mode),
    }
    try:
        tenants_doc = json.loads(tenants_path.read_text(encoding="utf-8"))
        tenants_doc["tenants"].extend([
            {"tenant_id": "tn-alpha", "name": "Alpha Tie", "region": "us-east"},
            {"tenant_id": "tn-zeta", "name": "Zeta Tie", "region": "us-east"},
        ])
        pools_doc = json.loads(pools_path.read_text(encoding="utf-8"))
        pools_doc["pools"].append({
            "pool_id": "sp-runtime-tie",
            "period_id": "2027-03",
            "total_cost_microcents": 100,
            "participants": ["tn-zeta", "tn-alpha", "tn-echo"],
        })
        for path, (_body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
        tenants_path.write_text(json.dumps(tenants_doc, indent=2) + "\n", encoding="utf-8")
        pools_path.write_text(json.dumps(pools_doc, indent=2) + "\n", encoding="utf-8")

        run_binary()
        swapped = load_output()
        expected = compute_ledger(DATA_DIR)
        assert swapped == expected
        alpha = find_tenant(swapped["tenants"], "tn-alpha")
        zeta = find_tenant(swapped["tenants"], "tn-zeta")
        echo = find_tenant(swapped["tenants"], "tn-echo")
        assert alpha["shared_allocated_microcents"] == 34
        assert echo["shared_allocated_microcents"] == 33
        assert zeta["shared_allocated_microcents"] == 33
        assert alpha["shared_allocated_microcents"] != zeta["shared_allocated_microcents"]
    finally:
        for path, (body, mode) in backups.items():
            os.chmod(path, mode | 0o200)
            path.write_bytes(body)
            os.chmod(path, mode)
        run_binary()


def test_runtime_stale_credit_period_id_ignored(ledger):
    """SCHEMA.md: credits outside billing period_id must not apply."""
    credits_path = DATA_DIR / "credits.ndjson"
    body, mode = credits_path.read_bytes(), credits_path.stat().st_mode
    try:
        os.chmod(credits_path, mode | 0o200)
        with credits_path.open("a", encoding="utf-8") as f:
            f.write(
                '{"credit_id": "cr-runtime-stale", "tenant_id": "tn-arc", '
                '"period_id": "2027-02", "amount_microcents": 500000}\n'
            )
        run_binary()
        swapped = load_output()
        expected = compute_ledger(DATA_DIR)
        assert swapped == expected
        arc = find_tenant(swapped["tenants"], "tn-arc")
        assert arc["credit_applied_microcents"] == 90000
        assert arc["credit_applied_microcents"] != 590000
        assert swapped["summary"]["credit_applied_microcents"] == 130000
    finally:
        os.chmod(credits_path, mode | 0o200)
        credits_path.write_bytes(body)
        os.chmod(credits_path, mode)
        run_binary()


def test_runtime_line_item_order_follows_config(ledger):
    """SCHEMA.md: line_items emit in config line_item_order, not alphabetical service names."""
    config_path = DATA_DIR / "config.json"
    body, mode = config_path.read_bytes(), config_path.stat().st_mode
    try:
        cfg = json.loads(config_path.read_text(encoding="utf-8"))
        cfg["line_item_order"] = ["egress", "storage", "compute"]
        os.chmod(config_path, mode | 0o200)
        config_path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
        run_binary()
        swapped = load_output()
        expected = compute_ledger(DATA_DIR)
        assert swapped == expected
        arc = find_tenant(swapped["tenants"], "tn-arc")
        services = [li["service"] for li in arc["line_items"]]
        assert services == ["egress", "storage", "compute"]
        assert services != sorted(services)
        assert services != ["compute", "egress", "storage"]
    finally:
        os.chmod(config_path, mode | 0o200)
        config_path.write_bytes(body)
        os.chmod(config_path, mode)
        run_binary()


def test_pledge_inputs_and_contracts_immutable_image_baselines():
    """SCHEMA.md: pledge_inputs and billing_contracts stay SHA256-identical to image baselines."""
    assert tree_fingerprint(DATA_DIR) == PLEDGE_INPUTS_BASELINE_FINGERPRINT
    assert tree_fingerprint(CONTRACTS_DIR) == BILLING_CONTRACTS_BASELINE_FINGERPRINT
    assert locked_engine_helper_fingerprint() == LOCKED_ENGINE_HELPER_FINGERPRINT


def test_pledge_inputs_contracts_write_permission_denied():
    """SCHEMA.md: bundled inputs are not writable; permission denied under nobody."""
    for root in (DATA_DIR, CONTRACTS_DIR):
        result = subprocess.run(
            [
                "su",
                "-s",
                "/bin/sh",
                "nobody",
                "-c",
                "echo x > %s" % (root / ".write_probe"),
            ],
            capture_output=True,
            text=True,
        )
        assert result.returncode != 0
        combined = (result.stderr + result.stdout).lower()
        assert "permission denied" in combined or "not permitted" in combined
    run_binary()
    assert tree_fingerprint(DATA_DIR) == PLEDGE_INPUTS_BASELINE_FINGERPRINT
    assert tree_fingerprint(CONTRACTS_DIR) == BILLING_CONTRACTS_BASELINE_FINGERPRINT
