"""Verifies /app/rabbitmq_definitions.json against
RABBITMQ_ACCESS_POLICY.md, cross referencing PERMISSION_CHANGELOG.md,
DOWNSTREAM_CONSUMERS.md, PROTECTED_SERVICE_ACCOUNTS.md, and
INCIDENT_ACCESS.md.

Independently derives the expected configure/write/read regex for every
(user, vhost, capability) combination from the tier table, documented
overrides, the permission changelog's latest-DATED-wins resolution
(never by file position), time-boxed incident access evaluated as of a
fixed current date, and the two independent confidential-tier budgets
(never importing or shelling out to solution/solve.sh), then checks
ACCESS DECISIONS for representative resource names rather than
comparing regex strings verbatim, so a differently-written but
equivalent pattern still passes.

The four reference documents and the seed's users/vhosts identity are
read from THIS directory (tests/), not from /app/ -- /app/*.md exist
only so the agent has something to read while solving. tests/ is a
separate, Harbor-managed copy the agent's own solving session never
touches, so an agent cannot pass by editing a reference file (or the
users/vhosts arrays) instead of fixing the permissions array.
"""

import json
import os
import re

APP = "/app"
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
DEFINITIONS = os.path.join(APP, "rabbitmq_definitions.json")
PRISTINE_SEED = os.path.join(TESTS_DIR, "rabbitmq_definitions.seed.json")
PERMISSION_CHANGELOG = os.path.join(TESTS_DIR, "PERMISSION_CHANGELOG.md")
DOWNSTREAM_CONSUMERS = os.path.join(TESTS_DIR, "DOWNSTREAM_CONSUMERS.md")
PROTECTED_SERVICE_ACCOUNTS = os.path.join(TESTS_DIR, "PROTECTED_SERVICE_ACCOUNTS.md")
INCIDENT_ACCESS = os.path.join(TESTS_DIR, "INCIDENT_ACCESS.md")

TODAY = "2026-07-16"
CAPS = ("configure", "write", "read")

# (tier, owning-team usernames, resource-name prefix)
TIERS = {
    "/billing": ("confidential", ["svc-billing-api", "svc-billing-worker"], "billing"),
    "/payments": ("confidential", ["svc-payments-gateway", "svc-payments-recon"], "payments"),
    "/audit-log": ("confidential", ["svc-audit-collector"], "audit-log"),
    "/orders": ("internal", ["svc-orders-api"], "orders"),
    "/fulfillment": ("internal", ["svc-fulfillment-worker"], "fulfillment"),
    "/reporting": ("internal", ["svc-reporting-etl"], "reporting"),
    "/public-status": ("public", ["svc-public-status-writer"], "public-status"),
}
CONFIDENTIAL_VHOSTS = ["/billing", "/payments", "/audit-log"]
CONFIGURE_BUDGET_CAP = 3
WRITE_BUDGET_CAP = 4

# representative resource names per vhost: an owned one, a foreign one
# that a too-broad pattern might wrongly match, plus any override/
# changelog-specific exact resource names.
REPRESENTATIVE_RESOURCES = {
    "/billing": ["billing.invoices", "billing.legacy-invoices", "billingclone.data"],
    "/payments": ["payments.ledger", "payments.dispute-notes", "paymentsclone.data"],
    "/audit-log": ["audit-log.access-events", "audit-logclone.data"],
    "/orders": ["orders.new", "ordersclone.data"],
    "/fulfillment": ["fulfillment.picks", "fulfillmentclone.data"],
    "/reporting": ["reporting.daily-rollup", "reportingclone.data"],
    "/public-status": ["public-status.incidents", "public-statusclone.data"],
}


# --- independent parsers -----------------------------------------------------


def load_json(path):
    with open(path) as f:
        return json.load(f)


def parse_changelog(path):
    """(user, vhost, capability) -> latest (date, regex-or-empty), among
    lines naming a real vhost only. File order is deliberately not
    chronological; only the DATE column decides which line wins."""
    latest = {}
    line_re = re.compile(
        r"^(\d{4}-\d{2}-\d{2})\s+\S+\s+(GRANT|REVOKE)\s+(\S+)\s+(\S+)\s+(configure|write|read)\s+(\S+)"
    )
    with open(path) as f:
        for line in f:
            m = line_re.match(line.strip())
            if not m:
                continue
            date, action, user, vhost, cap, value = m.groups()
            if vhost not in TIERS:
                continue
            regex = "" if action == "REVOKE" else value
            key = (user, vhost, cap)
            if key not in latest or date > latest[key][0]:
                latest[key] = (date, regex)
    return latest


def parse_name_list(path):
    names = set()
    with open(path) as f:
        for line in f:
            stripped = line.strip()
            if stripped and re.match(r"^[\w.-]+$", stripped):
                names.add(stripped)
    return names


def parse_incident_access(path):
    """List of (user, vhost, start, end)."""
    grants = []
    line_re = re.compile(r"^(\S+)\s+(/\S+)\s+(\d{4}-\d{2}-\d{2})\s+(\d{4}-\d{2}-\d{2})$")
    with open(path) as f:
        for line in f:
            m = line_re.match(line.strip())
            if m:
                grants.append(m.groups())
    return grants


PRISTINE = load_json(PRISTINE_SEED)
ALL_USERS = [u["name"] for u in PRISTINE["users"]]
TAGS = {u["name"]: set(u["tags"]) for u in PRISTINE["users"]}
CHANGELOG = parse_changelog(PERMISSION_CHANGELOG)
DOWNSTREAM = parse_name_list(DOWNSTREAM_CONSUMERS)
PROTECTED = parse_name_list(PROTECTED_SERVICE_ACCOUNTS)
INCIDENTS = parse_incident_access(INCIDENT_ACCESS)


def tag_of(user):
    tags = TAGS.get(user, set())
    if "administrator" in tags:
        return "administrator"
    if "monitoring" in tags:
        return "monitoring"
    return None


def prefix_pattern(prefix):
    return rf"^{prefix}\..*"


# --- independent ground-truth computation ------------------------------------


def build_expected_pre_budget():
    reg = {(u, v, c): "" for u in ALL_USERS for v in TIERS for c in CAPS}
    for vhost, (tier, owners, prefix) in TIERS.items():
        pat = prefix_pattern(prefix)
        for owner in owners:
            for cap in CAPS:
                reg[(owner, vhost, cap)] = pat
        if tier == "confidential" and vhost != "/audit-log":
            reg[("svc-audit-collector", vhost, "read")] = pat
        if tier == "public":
            for u in ALL_USERS:
                if u in owners or tag_of(u) is not None:
                    continue
                reg[(u, vhost, "read")] = pat
    # documented overrides
    reg[("svc-payments-gateway", "/billing", "read")] = r"^billing\.legacy-invoices$"
    for u in DOWNSTREAM:
        reg[(u, "/reporting", "read")] = prefix_pattern("reporting")
    # time-boxed incident access: applies only while TODAY falls inside
    # the grant's inclusive window; a window not covering TODAY has no
    # effect at all, as if the line were absent.
    for user, vhost, start, end in INCIDENTS:
        if vhost not in TIERS:
            continue
        if start <= TODAY <= end:
            _, _, prefix = TIERS[vhost]
            pat = prefix_pattern(prefix)
            reg[(user, vhost, "write")] = pat
            reg[(user, vhost, "read")] = pat
    # permission changelog: latest-DATED entry per (user, vhost,
    # capability) wins, superseding tier defaults, overrides, AND
    # incident access set above.
    for (user, vhost, cap), (_, regex) in CHANGELOG.items():
        reg[(user, vhost, cap)] = regex
    return reg


def apply_budget(reg, capability, cap_value):
    reg = dict(reg)
    holders = {
        v: {u for u in ALL_USERS if tag_of(u) is None and reg[(u, v, capability)]}
        for v in CONFIDENTIAL_VHOSTS
    }

    def combined_count():
        total = set()
        for v in CONFIDENTIAL_VHOSTS:
            total |= holders[v]
        return len(total)

    while combined_count() > cap_value:
        candidates = [v for v in CONFIDENTIAL_VHOSTS if holders[v] - PROTECTED]
        if not candidates:
            break
        max_len = max(len(holders[v]) for v in candidates)
        tied = sorted(v for v in candidates if len(holders[v]) == max_len)
        best = tied[0]
        removable = sorted(holders[best] - PROTECTED)
        victim = removable[-1]
        holders[best].discard(victim)
        reg[(victim, best, capability)] = ""

    return reg


EXPECTED = build_expected_pre_budget()
EXPECTED = apply_budget(EXPECTED, "configure", CONFIGURE_BUDGET_CAP)
EXPECTED = apply_budget(EXPECTED, "write", WRITE_BUDGET_CAP)
LIVE = load_json(DEFINITIONS)


def actual_regex_map():
    reg = {(u, v, c): "" for u in ALL_USERS for v in TIERS for c in CAPS}
    for entry in LIVE.get("permissions", []):
        user, vhost = entry.get("user"), entry.get("vhost")
        if user not in ALL_USERS or vhost not in TIERS:
            continue
        for cap in CAPS:
            reg[(user, vhost, cap)] = entry.get(cap, "")
    return reg


ACTUAL_RAW = actual_regex_map()


def effective_regex(regmap, user, vhost, cap):
    tag = tag_of(user)
    if tag == "administrator":
        return ".*"
    if tag == "monitoring":
        return ".*" if cap == "read" else ""
    return regmap.get((user, vhost, cap), "")


def allows(regex, resource):
    if not regex:
        return False
    try:
        return re.fullmatch(regex, resource) is not None
    except re.error:
        return False


def expected_access(user, vhost, cap, resource):
    return allows(effective_regex(EXPECTED, user, vhost, cap), resource)


def actual_access(user, vhost, cap, resource):
    return allows(effective_regex(ACTUAL_RAW, user, vhost, cap), resource)


def raw_holders(regmap, capability, vhost):
    return {u for u in ALL_USERS if tag_of(u) is None and regmap.get((u, vhost, capability), "")}


# --- structural invariants ---------------------------------------------------


def test_users_and_vhosts_identity_is_unmodified():
    """Only the permissions array is graded; users and vhosts must stay
    exactly as seeded (same accounts, same tags, same vhost list)."""
    assert LIVE.get("users") == PRISTINE["users"]
    assert LIVE.get("vhosts") == PRISTINE["vhosts"]


def test_reference_documents_are_unmodified():
    """PERMISSION_CHANGELOG.md, DOWNSTREAM_CONSUMERS.md,
    PROTECTED_SERVICE_ACCOUNTS.md, and INCIDENT_ACCESS.md are read-only
    reference material; this compares the agent's live /app/ copies
    against this tests/ directory's own untouched copies, so editing one
    of them to make a grant come out right (rather than fixing the
    permissions array) is caught directly."""
    for name in (
        "PERMISSION_CHANGELOG.md",
        "DOWNSTREAM_CONSUMERS.md",
        "PROTECTED_SERVICE_ACCOUNTS.md",
        "INCIDENT_ACCESS.md",
    ):
        with open(os.path.join(APP, name)) as f:
            app_content = f.read()
        with open(os.path.join(TESTS_DIR, name)) as f:
            reference_content = f.read()
        assert app_content == reference_content, f"/app/{name} was modified"


def test_tagged_users_have_no_explicit_permission_entries():
    """administrator/monitoring access comes entirely from the tag; an
    explicit permissions entry for a tagged user is redundant and must
    not be present."""
    tagged = [u for u in ALL_USERS if tag_of(u) is not None]
    entries_by_user = {}
    for entry in LIVE.get("permissions", []):
        entries_by_user.setdefault(entry.get("user"), []).append(entry.get("vhost"))
    for user in tagged:
        assert user not in entries_by_user, (
            f"{user} is tagged {tag_of(user)} but has explicit permissions entries on {entries_by_user[user]}"
        )


# --- per-(user, vhost, capability, resource) access-decision checks ---------


def _assert_access_matches_expected(user, vhost):
    for cap in CAPS:
        for resource in REPRESENTATIVE_RESOURCES[vhost]:
            exp = expected_access(user, vhost, cap, resource)
            act = actual_access(user, vhost, cap, resource)
            assert act == exp, (
                f"{user} {cap} on {vhost} resource {resource!r}: expected {exp}, got {act}"
            )


def test_billing_owning_team_access():
    """svc-billing-api keeps full access; svc-billing-worker's write went
    through a REVOKE-then-GRANT changelog chain that nets back to the
    tier default (must be read by DATE, not by file position), while its
    configure is the one cleared by the confidential-tier budget trim."""
    _assert_access_matches_expected("svc-billing-api", "/billing")
    _assert_access_matches_expected("svc-billing-worker", "/billing")


def test_billing_cross_team_grants():
    """svc-audit-collector's stale write grant on /billing must be
    cleared, AND a later changelog ticket separately revokes its normal
    confidential-tier read grant on billing specifically (leaving it no
    access to billing at all), while svc-payments-gateway's documented
    override stays scoped to the exact legacy-invoices resource only."""
    _assert_access_matches_expected("svc-audit-collector", "/billing")
    _assert_access_matches_expected("svc-payments-gateway", "/billing")


def test_payments_owning_team_access():
    """svc-payments-gateway keeps full access; svc-payments-recon's
    configure must be revoked per the changelog's latest ticket even
    though an earlier ticket and the tier default both granted it, and
    its write is separately cleared by the write budget."""
    _assert_access_matches_expected("svc-payments-gateway", "/payments")
    _assert_access_matches_expected("svc-payments-recon", "/payments")


def test_payments_audit_collector_changelog_addition():
    """svc-audit-collector's normal confidential-tier read grant on
    /payments is extended by a changelog-only write exception scoped to
    the single exact resource payments.dispute-notes, which the tier
    table alone would never produce."""
    _assert_access_matches_expected("svc-audit-collector", "/payments")


def test_audit_log_excludes_the_cross_confidential_read_rule():
    """/audit-log's documented override means nobody besides the owning
    team has any grant here, and the auditor-reads-other-confidential-
    vhosts rule does not apply to audit-log itself."""
    _assert_access_matches_expected("svc-audit-collector", "/audit-log")
    _assert_access_matches_expected("svc-billing-api", "/audit-log")


def test_orders_grant_is_scoped_to_its_own_prefix():
    """The seed's wildcard '.*' pattern must be tightened to the orders
    prefix only, or the foreign resource check below fails. A changelog
    line naming a misspelled vhost ('/reporing') must be ignored
    entirely -- it never refers to any real vhost."""
    _assert_access_matches_expected("svc-orders-api", "/orders")


def test_fulfillment_grant_is_present():
    """The seed omits svc-fulfillment-worker's owning-team entry on
    /fulfillment entirely."""
    _assert_access_matches_expected("svc-fulfillment-worker", "/fulfillment")


def test_reporting_owning_team_and_downstream_consumer_split():
    """DOWNSTREAM_CONSUMERS.md names two services, but a later changelog
    ticket revokes read specifically for one of them (svc-fulfillment-
    worker), so only svc-orders-api actually keeps the override's read
    grant -- a changelog entry can cancel an override for one named
    party without affecting the other. svc-orders-api's own /reporting
    write went through a GRANT-then-REVOKE chain that must net to no
    write, matching what the override (read-only) already implied."""
    _assert_access_matches_expected("svc-reporting-etl", "/reporting")
    _assert_access_matches_expected("svc-orders-api", "/reporting")
    _assert_access_matches_expected("svc-fulfillment-worker", "/reporting")


def test_public_status_broadcast_read_coverage():
    """Every non-tagged user besides the owner needs an explicit
    read-only grant on /public-status, including svc-incident-responder;
    missing even one fails."""
    for user in ALL_USERS:
        if tag_of(user) is not None:
            continue
        _assert_access_matches_expected(user, "/public-status")


def test_tagged_users_effective_access():
    """svc-platform-admin (administrator) gets full access everywhere;
    svc-monitoring-agent (monitoring) gets read everywhere and nothing
    else, regardless of the (absent) permissions entries."""
    for vhost in TIERS:
        _assert_access_matches_expected("svc-platform-admin", vhost)
        _assert_access_matches_expected("svc-monitoring-agent", vhost)


def test_incident_responder_only_gets_the_currently_active_window():
    """INCIDENT_ACCESS.md lists two windows for svc-incident-responder:
    the /payments window already ended before the evaluation date and
    must have no effect, while the /orders window is currently active
    and must grant write+read (never configure) scoped to orders. A
    naive agent that copies the reference file's grants verbatim without
    comparing dates gets both of these backwards or grants both."""
    _assert_access_matches_expected("svc-incident-responder", "/payments")
    _assert_access_matches_expected("svc-incident-responder", "/orders")


# --- cross-entity budgets -----------------------------------------------------


def test_confidential_configure_budget_is_not_exceeded():
    """The combined distinct configure-holder count across billing,
    payments, and audit-log must not exceed its cap, only knowable after
    resolving all three vhosts' configure grants. Counts explicit
    permissions-array grants only -- tag-derived and incident-derived
    access are fixed facts the agent cannot trim, so both are out of
    scope for this budget."""
    holders = set()
    for vhost in CONFIDENTIAL_VHOSTS:
        holders |= raw_holders(ACTUAL_RAW, "configure", vhost)
    assert len(holders) <= CONFIGURE_BUDGET_CAP, (
        f"{len(holders)} distinct users hold confidential configure access, "
        f"cap is {CONFIGURE_BUDGET_CAP}: {sorted(holders)}"
    )


def test_confidential_write_budget_is_not_exceeded():
    """A SEPARATE budget on write access across the same three vhosts;
    clearing a user's configure to satisfy the first budget does not
    automatically satisfy this one, and vice versa -- both must be
    checked independently."""
    holders = set()
    for vhost in CONFIDENTIAL_VHOSTS:
        holders |= raw_holders(ACTUAL_RAW, "write", vhost)
    assert len(holders) <= WRITE_BUDGET_CAP, (
        f"{len(holders)} distinct users hold confidential write access, "
        f"cap is {WRITE_BUDGET_CAP}: {sorted(holders)}"
    )


def test_protected_account_keeps_configure_and_write_access():
    """svc-billing-api is on PROTECTED_SERVICE_ACCOUNTS.md and eligible
    via the billing owning-team grant, so neither budget's trim may ever
    clear its configure or write access."""
    assert actual_access("svc-billing-api", "/billing", "configure", "billing.invoices")
    assert actual_access("svc-billing-api", "/billing", "write", "billing.invoices")


def test_trimmed_users_keep_their_other_capabilities():
    """The configure budget only clears configure (svc-billing-worker
    keeps write/read); the write budget only clears write
    (svc-payments-recon keeps read, and its configure was already
    cleared by the changelog, not by this budget)."""
    assert actual_access("svc-billing-worker", "/billing", "write", "billing.invoices")
    assert actual_access("svc-billing-worker", "/billing", "read", "billing.invoices")
    assert not actual_access("svc-billing-worker", "/billing", "configure", "billing.invoices")
    assert actual_access("svc-payments-recon", "/payments", "read", "payments.ledger")
    assert not actual_access("svc-payments-recon", "/payments", "write", "payments.ledger")
    assert not actual_access("svc-payments-recon", "/payments", "configure", "payments.ledger")


# --- self-check on the budget-trim algorithm's untested branches ------------


def _run_trim(holders, protected, cap):
    def combined_count():
        total = set()
        for v in holders:
            total |= holders[v]
        return len(total)

    while combined_count() > cap:
        candidates = [v for v in holders if holders[v] - protected]
        max_len = max(len(holders[v]) for v in candidates)
        tied = sorted(v for v in candidates if len(holders[v]) == max_len)
        best = tied[0]
        removable = sorted(holders[best] - protected)
        holders[best].discard(removable[-1])
    return holders


def test_budget_trim_algorithm_cascades_to_the_next_vhost_when_needed():
    """A synthetic scenario distinct from the real fixture, exercising
    the 'move to next-highest vhost' and 'multiple removals from one
    vhost' branches the real fixture's single-user, single-vhost trims
    never reach on their own."""
    holders = {"/billing": {"a", "b", "c"}, "/payments": {"d", "e", "f"}, "/audit-log": set()}
    result = _run_trim(holders, set(), 2)
    total = set()
    for v in result:
        total |= result[v]
    assert len(total) == 2
    assert result["/billing"] == {"a"}
    assert result["/payments"] == {"d"}
