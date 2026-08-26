"""Black-box tests for crosspay: the SQLite payroll core (employees, hours,
gross, progressive half-even withholding) and the country commands (currency +
continent lookup from the bundled dataset, region schedule selection and
minor-unit rounding) against pinned, drift-proof ISO country codes. Every
expected figure is recomputed independently from the documented schedule
constants and the pinned dataset answers."""
import os
import subprocess
import time

import pytest

APP_DIR = "/app"
BINARY = "/app/crosspay"
DB = "/app/data/crosspay.db"


@pytest.fixture(scope="module", autouse=True)
def build_binary():
    """Build the binary once and start from an empty database."""
    result = subprocess.run(
        ["go", "build", "-o", BINARY, "."],
        cwd=APP_DIR, capture_output=True, text=True,
    )
    if result.returncode != 0:
        pytest.fail(f"go build failed:\n{result.stderr}")
    try:
        os.remove(DB)
    except FileNotFoundError:
        pass
    r = run(["init"])
    assert r.returncode == 0 and r.stdout.strip() == "ok", r.stdout + r.stderr


def run(args):
    return subprocess.run([BINARY] + list(args), capture_output=True, text=True)


def run_live(args, tries=5):
    """Run a country-data command. The dataset is local so this resolves in one
    shot; the retry loop is a harmless guard kept for symmetry."""
    r = run(args)
    attempt = 1
    while attempt < tries and r.stdout.strip() == "data_error":
        time.sleep(attempt)
        r = run(args)
        attempt += 1
    return r


def out(args):
    r = run(args)
    assert r.returncode == 0, r.stdout + r.stderr
    return r.stdout.strip()


# --- independent recomputation of the documented payroll math ----------------

OPEN = 1 << 62
SCHEDULES = {
    "ASIA": [(10000000, 500), (50000000, 1500), (200000000, 2500), (OPEN, 3500)],
    "EUROPE": [(12000000, 800), (40000000, 2000), (150000000, 3000), (OPEN, 4200)],
    "OCEANIA": [(18000000, 1000), (60000000, 2200), (OPEN, 3700)],
    "AMERICAS": [(11000000, 1000), (45000000, 2400), (OPEN, 3200)],
    "AFRICA": [(9000000, 700), (35000000, 1800), (OPEN, 3000)],
}


def bankers_round(num, den):
    q, r = divmod(num, den)
    twice = r * 2
    if twice < den:
        return q
    if twice > den:
        return q + 1
    return q if q % 2 == 0 else q + 1


def half_up(num, den):
    """Naive round-half-up, used only to show it disagrees with half-even on an
    exact-half tie whose floor quotient is even."""
    q, r = divmod(num, den)
    if r * 2 < den:
        return q
    return q + 1


def withhold(gross, region):
    sched = SCHEDULES[region]
    total = 0
    lower = 0
    for i, (upto, bp) in enumerate(sched):
        upper = gross if i == len(sched) - 1 else upto
        if upper > gross:
            upper = gross
        sl = upper - lower
        if sl < 0:
            sl = 0
        total += bankers_round(sl * bp, 10000)
        lower = upto
    return total


MINOR = {"JPY": 0, "BHD": 3, "KWD": 3, "EUR": 2, "GBP": 2, "SEK": 2, "INR": 2, "AUD": 2, "USD": 2}


def round_to_minor(micros, cur):
    return bankers_round(micros, 10 ** (6 - MINOR[cur]))


# Lever 1: employer social contribution (region rule + per-country floor/cap).
SOCIAL = {  # region -> (rate_bp, cap_micros)
    "ASIA": (900, 120000000),
    "EUROPE": (1300, 100000000),
    "OCEANIA": (1050, 90000000),
    "AMERICAS": (765, 130000000),
    "AFRICA": (600, 80000000),
}
FLOOR = {  # country code -> contributory-base floor
    "JP": 20000000, "BH": 125000000, "KW": 15000000, "IN": 8000000,
    "DE": 25000000, "GB": 22000000, "SE": 24000000, "AU": 18000000,
    "FR": 25000000, "IT": 25000000, "ES": 25000000,
}


def social(gross, region, country):
    rate, cap = SOCIAL[region]
    base = max(gross, FLOOR[country])
    if base > cap:
        base = cap
    return bankers_round(base * rate, 10000)


# Lever 2: conversion to the base currency through the pivot currency.
PIVOT_RATE = {  # micro-units of pivot per one whole major unit
    "USD": 752000, "XDR": 1000000, "JPY": 5100, "INR": 9050,
    "BHD": 1994000, "KWD": 2440000, "EUR": 815000, "GBP": 953000,
    "SEK": 71500, "AUD": 496000,
}
BASE_CUR = "USD"


def convert_base(amount, cur):
    leg1 = bankers_round(amount * PIVOT_RATE[cur], 1000000)
    return bankers_round(leg1 * 1000000, PIVOT_RATE[BASE_CUR])


def convert_direct(amount, cur):
    # The wrong single-rounding shortcut the pivot rule must NOT reduce to.
    return bankers_round(amount * PIVOT_RATE[cur], PIVOT_RATE[BASE_CUR])


def convert_from_base(amount, cur):
    leg1 = bankers_round(amount * PIVOT_RATE[BASE_CUR], 1000000)
    return bankers_round(leg1 * 1000000, PIVOT_RATE[cur])


# Lever 3: the global employer social-contribution ceiling enforced once per
# `report` run, apportioned across countries by largest-remainder.
GLOBAL_SOCIAL_CAP = 100000000


def apply_global_social_cap(raw_local, currencies):
    """raw_local: {country: raw local social subtotal}. Returns the adjusted
    local subtotals after enforcing GLOBAL_SOCIAL_CAP, largest-remainder style,
    matching docs/spec.md exactly."""
    raw_base = {cc: convert_base(v, currencies[cc]) for cc, v in raw_local.items()}
    total = sum(raw_base.values())
    if total <= GLOBAL_SOCIAL_CAP or total == 0:
        return dict(raw_local)
    floors, remainders = {}, {}
    for cc, b in raw_base.items():
        num = b * GLOBAL_SOCIAL_CAP
        floors[cc] = num // total
        remainders[cc] = num % total
    deficit = GLOBAL_SOCIAL_CAP - sum(floors.values())
    ranked = sorted(raw_base.keys(), key=lambda cc: (-remainders[cc], cc))
    adjusted_base = dict(floors)
    for cc in ranked[:deficit]:
        adjusted_base[cc] += 1
    return {cc: convert_from_base(adjusted_base[cc], currencies[cc]) for cc in raw_local}


# Pinned, drift-proof answers from the bundled dataset. Currency + continent
# are fixed for these ISO codes; the tests assert them and recompute from them.
PINNED = {
    "JP": ("JPY", "Asia"), "BH": ("BHD", "Asia"), "KW": ("KWD", "Asia"),
    "IN": ("INR", "Asia"), "DE": ("EUR", "Europe"), "GB": ("GBP", "Europe"),
    "SE": ("SEK", "Europe"), "AU": ("AUD", "Oceania"),
}
CONTINENT_REGION = {"Asia": "ASIA", "Europe": "EUROPE", "Oceania": "OCEANIA"}


# --- offline: employees, hours, gross ----------------------------------------

def test_add_and_list_employees():
    assert out(["add-employee", "alice", "--rate", "7500000"]).isdigit()
    assert out(["add-employee", "bob", "--rate", "12250000"]).isdigit()
    assert out(["employees"]) == "alice 7500000\nbob 12250000"


def test_duplicate_employee_exists():
    r = run(["add-employee", "alice", "--rate", "5000000"])
    assert r.returncode != 0 and r.stdout.strip() == "exists"


def test_bad_rate():
    for bad in ["0", "-3", "abc"]:
        r = run(["add-employee", "x" + bad, "--rate", bad])
        assert r.returncode != 0 and r.stdout.strip() == "bad_rate"


def test_log_hours_and_gross_accumulates():
    out(["add-employee", "carol", "--rate", "4000000"])
    out(["log-hours", "carol", "40", "--now", "1700000000"])
    out(["log-hours", "carol", "8", "--now", "1700086400"])
    assert out(["gross", "carol"]) == str(48 * 4000000)


def test_gross_no_hours_zero():
    out(["add-employee", "dave", "--rate", "9000000"])
    assert out(["gross", "dave"]) == "0"


def test_unknown_employee_not_found():
    for cmd in [["gross", "ghost"], ["log-hours", "ghost", "3", "--now", "1"],
                ["net", "ghost", "--region", "ASIA"]]:
        r = run(cmd)
        assert r.returncode != 0 and r.stdout.strip() == "not_found"


# --- offline: schedules and withholding --------------------------------------

def test_schedules_listing():
    assert out(["schedules"]) == "AFRICA\nAMERICAS\nASIA\nEUROPE\nOCEANIA"


def test_bad_region():
    r = run(["withhold", "--region", "MARS", "--gross", "1000"])
    assert r.returncode != 0 and r.stdout.strip() == "bad_region"


@pytest.mark.parametrize("region,gross", [
    ("ASIA", 95333329), ("ASIA", 6000000), ("ASIA", 250000000),
    ("EUROPE", 95333329), ("EUROPE", 12000000), ("OCEANIA", 77777777),
    ("AMERICAS", 45000001), ("AFRICA", 8999999),
    ("EUROPE", 150000025), ("OCEANIA", 60000050),
])
def test_withhold_vectors(region, gross):
    assert out(["withhold", "--region", region, "--gross", str(gross)]) == str(withhold(gross, region))


def test_withhold_exact_half_tie_diverges_from_half_up():
    """EUROPE at gross 150000025 taxes its last 25 micro-units of open-ended slice
    at 4200 bp: 25*4200 = 105000, and 105000/10000 = 10.5 exactly. The floor 10 is
    even, so half-to-even keeps the tier's contribution at 10 while a naive
    round-half-up would give 11, changing the schedule total by one micro-unit.
    OCEANIA at 60000050 hits the same shape one tier earlier (its open-ended rate
    is 3700 bp): 50*3700 = 185000, 185000/10000 = 18.5 exactly, floor 18 even."""
    eu_slice_num, eu_den = 25 * 4200, 10000
    assert bankers_round(eu_slice_num, eu_den) == 10
    assert half_up(eu_slice_num, eu_den) == 11
    assert withhold(150000025, "EUROPE") == 39560010
    assert out(["withhold", "--region", "EUROPE", "--gross", "150000025"]) == "39560010"

    oc_slice_num, oc_den = 50 * 3700, 10000
    assert bankers_round(oc_slice_num, oc_den) == 18
    assert half_up(oc_slice_num, oc_den) == 19
    assert withhold(60000050, "OCEANIA") == 11040018
    assert out(["withhold", "--region", "OCEANIA", "--gross", "60000050"]) == "11040018"


def test_net_matches_gross_minus_withhold():
    out(["add-employee", "erin", "--rate", "7333333"])
    out(["log-hours", "erin", "13", "--now", "1700000000"])
    gross = 13 * 7333333
    assert out(["gross", "erin"]) == str(gross)
    expected = gross - withhold(gross, "EUROPE")
    assert out(["net", "erin", "--region", "EUROPE"]) == str(expected)


# --- dataset: country metadata -----------------------------------------------

@pytest.mark.parametrize("code", list(PINNED.keys()))
def test_country_info(code):
    cur, cont = PINNED[code]
    r = run_live(["country-info", "--country", code])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == f"{code} {cur} {cont}"


def test_country_info_unknown():
    r = run_live(["country-info", "--country", "ZZ"])
    assert r.returncode != 0 and r.stdout.strip() == "not_found"


# --- dataset: cross-border pay with per-currency minor-unit rounding ---------

@pytest.mark.parametrize("code", list(PINNED.keys()))
def test_country_pay(code):
    # A worker whose gross crosses several tiers and rounds non-trivially.
    name = "intl_" + code
    out(["add-employee", name, "--rate", "7333333"])
    out(["log-hours", name, "13", "--now", "1700000000"])
    gross = 13 * 7333333

    cur, cont = PINNED[code]
    region = CONTINENT_REGION[cont]
    wh = withhold(gross, region)
    net = gross - wh
    expected = "%s %s %d %d %d" % (
        code, cur,
        round_to_minor(gross, cur),
        round_to_minor(wh, cur),
        round_to_minor(net, cur),
    )
    r = run_live(["country-pay", name, "--country", code])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == expected


def test_same_region_different_minor_units():
    # JP, IN and BH are all Asia (same schedule) but JPY/INR/BHD carry 0/2/3
    # minor digits, so the same gross must round to three different figures.
    name = "spread"
    out(["add-employee", name, "--rate", "7333333"])
    out(["log-hours", name, "13", "--now", "1700000000"])
    gross = 13 * 7333333
    wh = withhold(gross, "ASIA")
    net = gross - wh
    seen = {}
    for code in ("JP", "IN", "BH"):
        cur = PINNED[code][0]
        r = run_live(["country-pay", name, "--country", code])
        assert r.returncode == 0, r.stdout + r.stderr
        seen[code] = r.stdout.strip().split()[-1]
        assert r.stdout.strip().endswith(str(round_to_minor(net, cur)))
    assert len({seen["JP"], seen["IN"], seen["BH"]}) == 3


# --- lever 1: employer social contribution (dataset region + country floor/cap)

@pytest.mark.parametrize("code,rate,hours", [
    ("JP", 1000000, 5),      # gross below floor -> base pinned to the floor
    ("JP", 7333333, 13),     # gross between floor and cap -> base is gross
    ("AU", 9000000, 20),     # gross above cap -> base pinned to the region cap
    ("DE", 5000000, 40),     # gross above cap -> base pinned to the region cap
    ("IN", 7333333, 13),     # different country floor, same Asia rule
    ("BH", 200000, 5),       # BH's own floor exceeds the Asia cap: any gross
    ("BH", 5000000, 8),      # ends up pinned to the cap, never to the floor
])
def test_social_vectors(code, rate, hours):
    name = "soc_%s_%d_%d" % (code, rate, hours)
    out(["add-employee", name, "--rate", str(rate)])
    out(["log-hours", name, str(hours), "--now", "1700000000"])
    gross = rate * hours
    region = CONTINENT_REGION[PINNED[code][1]]
    r = run_live(["social", name, "--country", code])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == str(social(gross, region, code))


def test_social_exact_half_tie_diverges_from_half_up():
    """A JP employee grossing 20000050 (above the 20000000 floor, so the base is
    the gross itself, untouched by the floor or the 120000000 cap) charges Asia's
    900 bp rate on that base: 20000050*900 = 18000045000, and dividing by 10000
    gives exactly 1800004.5. The floor 1800004 is even, so half-to-even keeps the
    contribution there while a naive round-half-up would post 1800005."""
    name = "soc_tie_jp"
    out(["add-employee", name, "--rate", "20000050"])
    out(["log-hours", name, "1", "--now", "1700000000"])
    gross = 20000050
    num, den = gross * 900, 10000
    assert bankers_round(num, den) == 1800004
    assert half_up(num, den) == 1800005
    assert social(gross, "ASIA", "JP") == 1800004
    r = run_live(["social", name, "--country", "JP"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "1800004"


def test_social_floor_above_cap_order_matters():
    """BH's own contributory-base floor (125000000) exceeds the Asia region cap
    (120000000), the one pinned country where that happens. Raising the base to
    the floor and then lowering it to the cap always lands on the cap (base
    120000000, contribution 10800000) no matter how small the gross is. Clamping
    in the other order -- capping first, then flooring -- lands on the floor
    instead (base 125000000, contribution 11250000), a different number. A low
    gross that would otherwise sit far under both bounds makes the two orders
    diverge cleanly."""
    name = "soc_order_bh"
    out(["add-employee", name, "--rate", "500000"])
    out(["log-hours", name, "2", "--now", "1700000000"])
    gross = 1000000
    floor_then_cap = social(gross, "ASIA", "BH")
    assert floor_then_cap == 10800000

    rate, cap = SOCIAL["ASIA"]
    cap_then_floor = bankers_round(max(min(gross, cap), FLOOR["BH"]) * rate, 10000)
    assert cap_then_floor == 11250000
    assert floor_then_cap != cap_then_floor

    r = run_live(["social", name, "--country", "BH"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == "10800000"


def test_social_unknown_country_not_found():
    out(["add-employee", "soc_ghost", "--rate", "5000000"])
    r = run_live(["social", "soc_ghost", "--country", "ZZ"])
    assert r.returncode != 0 and r.stdout.strip() == "not_found"


# --- lever 2: currency conversion through the pivot (offline) -----------------

@pytest.mark.parametrize("cur,amount", [
    ("EUR", 13), ("AUD", 1), ("KWD", 3), ("JPY", 74),
    ("EUR", 213000000), ("USD", 5000000), ("GBP", 7333333), ("INR", 103913329),
    ("EUR", 300),
])
def test_convert_offline(cur, amount):
    assert out(["convert", "--amount", str(amount), "--from", cur]) == str(convert_base(amount, cur))


def test_convert_exact_half_tie_first_leg_diverges_from_half_up():
    """Converting 300 EUR micro-units to the pivot is an exact half:
    300*815000 = 244500000, and 244500000/1000000 = 244.5 exactly. The floor 244
    is even, so half-to-even keeps the first leg at 244 (pivot micro-units) while
    a naive round-half-up would carry 245 into the second leg, and the two-leg
    result ends up 324 (half-even) versus 326 (half-up carried through)."""
    num, den = 300 * 815000, 1000000
    assert bankers_round(num, den) == 244
    assert half_up(num, den) == 245
    assert convert_base(300, "EUR") == 324
    assert out(["convert", "--amount", "300", "--from", "EUR"]) == "324"


@pytest.mark.parametrize("cur,amount", [("EUR", 13), ("AUD", 1), ("KWD", 3), ("JPY", 74)])
def test_convert_is_two_leg_not_direct(cur, amount):
    # These amounts are chosen so the two-leg pivot answer differs from the
    # single-rounding direct shortcut; the binary must match the two-leg answer.
    got = out(["convert", "--amount", str(amount), "--from", cur])
    assert convert_base(amount, cur) != convert_direct(amount, cur)
    assert got == str(convert_base(amount, cur))
    assert got != str(convert_direct(amount, cur))


def test_convert_bad_currency():
    r = run(["convert", "--amount", "100", "--from", "ZZZ"])
    assert r.returncode != 0 and r.stdout.strip() == "bad_currency"


# --- lever 3: aggregated, ranked cross-border report (dataset per country) ---

def test_assign_unknown_employee_not_found():
    r = run(["assign", "ghost_person", "--country", "JP"])
    assert r.returncode != 0 and r.stdout.strip() == "not_found"


def test_report_ranked_multicurrency():
    # DE, ES, FR and IT are all EUR/Europe. On RAW (uncapped) numbers they are
    # engineered to land on the exact same base cost, and DE/ES/FR (count 1
    # each) sort alphabetically among themselves while IT (count 2) would win
    # the tie on the employee-count rule -- the classic count-tie-break trap.
    # GB then pushes the run's combined social-contribution spend, once every
    # country's raw subtotal is independently converted to the base currency,
    # over GLOBAL_SOCIAL_CAP. That forces the largest-remainder cutback in
    # docs/spec.md, and DE/ES/FR/IT do NOT shrink by the same proportion: IT's
    # raw social subtotal is larger, so its absolute cutback is larger too,
    # which breaks the four-way base-cost tie and drops IT from first to last
    # among that quartet -- the opposite of what the raw numbers alone predict.
    # An implementation that ignores the cap (or applies it only to the report
    # total rather than to social alone, or converts the adjusted share back
    # with the forward pivot formula instead of the reverse one) reproduces the
    # raw ranking or a different wrong one, not this one.
    scenario = {
        "JP": [("rpt_wa", 7333333, 13), ("rpt_wc", 1000000, 5)],
        "DE": [("rpt_de1", 5325000, 40)],
        "ES": [("rpt_es1", 5325000, 40)],
        "FR": [("rpt_fr1", 5325000, 40)],
        "IT": [("rpt_it1", 5000000, 10), ("rpt_it2", 156500000, 1)],
        "AU": [("rpt_au1", 9000000, 20)],
        "GB": [("rpt_gb1", 15000000, 10), ("rpt_gb2", 7500000, 20)],
    }
    meta = {
        "JP": ("JPY", "Asia"), "DE": ("EUR", "Europe"), "FR": ("EUR", "Europe"),
        "IT": ("EUR", "Europe"), "ES": ("EUR", "Europe"), "AU": ("AUD", "Oceania"),
        "GB": ("GBP", "Europe"),
    }
    for cc, members in scenario.items():
        for name, rate, hours in members:
            out(["add-employee", name, "--rate", str(rate)])
            out(["log-hours", name, str(hours), "--now", "1700000000"])
            assert out(["assign", name, "--country", cc]) == "ok"

    # Re-recording the same employee/country pairing is rejected.
    dup = scenario["JP"][0][0]
    r = run(["assign", dup, "--country", "JP"])
    assert r.returncode != 0 and r.stdout.strip() == "exists"

    gross_local, raw_social_local, currencies = {}, {}, {}
    for cc, members in scenario.items():
        cur, cont = meta[cc]
        region = CONTINENT_REGION[cont]
        currencies[cc] = cur
        g_total = s_total = 0
        for name, rate, hours in members:
            gross = rate * hours
            g_total += gross
            s_total += social(gross, region, cc)
        gross_local[cc] = g_total
        raw_social_local[cc] = s_total

    # This is the raw (uncapped) total that would fall below the cap if GB were
    # left out -- confirming GB alone is what tips the run over the ceiling.
    assert sum(convert_base(v, currencies[cc]) for cc, v in raw_social_local.items()
               if cc != "GB") <= GLOBAL_SOCIAL_CAP
    adjusted_social = apply_global_social_cap(raw_social_local, currencies)
    assert sum(convert_base(adjusted_social[cc], currencies[cc]) for cc in scenario) <= GLOBAL_SOCIAL_CAP

    rows = []
    for cc, members in scenario.items():
        cur = currencies[cc]
        local = gross_local[cc] + adjusted_social[cc]
        rows.append((cc, cur, len(members), convert_base(local, cur)))
    rows.sort(key=lambda t: (-t[3], -t[2], t[0]))
    expected = "\n".join(
        "%d %s %s %d %d" % (i + 1, cc, cur, cnt, base)
        for i, (cc, cur, cnt, base) in enumerate(rows)
    )
    r = run_live(["report"])
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == expected
