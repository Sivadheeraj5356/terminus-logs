"""Independent dual reference for the Sender Authorization Policy.

Implements, from scratch and sharing no code with the engine, a single
fault-parameterized evaluator:

    decide(zone, domain, ip, faults)

with ``faults`` a subset of ``ALL_FAULTS``. ``faults=frozenset()`` is the
INTENDED semantics of docs/sap-spec.md Part 1. ``faults=ALL_FAULTS`` is the
DEPLOYED behaviour of the frozen engine. Proper subsets are the partial models a
solver gets by reasoning about one deviation at a time; the verifier uses them to
attribute divergences and to prove that no partial model scores.
"""

LOOKUP_LIMIT = 8
MAX_DELEGATION = 32
RESULTS = {"PASS", "FAIL", "SOFTFAIL", "NEUTRAL", "NONE", "PERMERROR"}
QMAP = {"+": "PASS", "-": "FAIL", "~": "SOFTFAIL", "?": "NEUTRAL"}

# The four respects in which the deployed engine departs from Part 1.
F_REQ = "req-drift"  # a delegation re-homes the subject domain
F_BUDGET = "budget-redirect"  # the redirect term is not charged
F_LAST = "last-match"  # the last matching directive settles, not the first
F_CIDR = "cidr-octet"  # an ip4 prefix is truncated to a whole octet
ALL_FAULTS = frozenset({F_REQ, F_BUDGET, F_LAST, F_CIDR})


class PermError(Exception):
    pass


# ---------------------------------------------------------------------------
# IPv4 + CIDR
# ---------------------------------------------------------------------------
def parse_ip(s):
    parts = s.split(".")
    if len(parts) != 4:
        raise ValueError("ip")
    v = 0
    for p in parts:
        if not p.isdigit() or (len(p) > 1 and p[0] == "0"):
            raise ValueError("octet")
        n = int(p)
        if n > 255:
            raise ValueError("octet range")
        v = (v << 8) | n
    return v


def ip_to_str(v):
    return "%d.%d.%d.%d" % ((v >> 24) & 255, (v >> 16) & 255, (v >> 8) & 255, v & 255)


def parse_cidr(body):
    if "/" in body:
        addr, ps = body.split("/", 1)
        if not ps.isdigit():
            return None
        prefix = int(ps)
        if prefix > 32:
            return None
    else:
        addr, prefix = body, 32
    try:
        net = parse_ip(addr)
    except ValueError:
        return None
    return (net, prefix)


def cidr_contains(ip, net, prefix, faults=frozenset()):
    if F_CIDR in faults:
        prefix = (prefix // 8) * 8
    if prefix == 0:
        return True
    host = 32 - prefix
    return (ip >> host) == (net >> host)


# ---------------------------------------------------------------------------
# Policy parsing (shape only; identical under every fault set)
# ---------------------------------------------------------------------------
class Term:
    __slots__ = ("raw", "qual", "mech", "arg", "cidr")

    def __init__(self, raw, qual, mech, arg=None, cidr=None):
        self.raw = raw
        self.qual = qual
        self.mech = mech
        self.arg = arg
        self.cidr = cidr


class Policy:
    __slots__ = ("directives", "redirect", "has_all")

    def __init__(self, directives, redirect, has_all):
        self.directives = directives
        self.redirect = redirect
        self.has_all = has_all


def parse_policy(text):
    toks = text.split()
    if not toks or toks[0] != "v=sap1":
        raise PermError("version")
    directives = []
    redirect = None
    has_all = False
    for tok in toks[1:]:
        if tok.startswith("redirect="):
            if redirect is not None:
                raise PermError("duplicate redirect")
            redirect = tok[len("redirect=") :]
            if not redirect:
                raise PermError("empty redirect")
            continue
        qual = "+"
        body = tok
        if body[:1] in ("+", "-", "~", "?"):
            qual = body[0]
            body = body[1:]
        if body == "all":
            has_all = True
            directives.append(Term(tok, qual, "all"))
        elif body == "a":
            directives.append(Term(tok, qual, "a", None))
        elif body.startswith("a:"):
            directives.append(Term(tok, qual, "a", body[2:]))
        elif body == "mx":
            directives.append(Term(tok, qual, "mx", None))
        elif body.startswith("mx:"):
            directives.append(Term(tok, qual, "mx", body[3:]))
        elif body.startswith("ip4:"):
            c = parse_cidr(body[4:])
            if c is None:
                raise PermError("bad ip4")
            directives.append(Term(tok, qual, "ip4", None, c))
        elif body.startswith("include:"):
            arg = body[len("include:") :]
            if not arg:
                raise PermError("empty include")
            directives.append(Term(tok, qual, "include", arg))
        else:
            raise PermError("unknown mechanism: " + tok)
    return Policy(directives, redirect, has_all)


# ---------------------------------------------------------------------------
# Zone lookups (unparseable addresses are dropped)
# ---------------------------------------------------------------------------
def a_records(zone, domain):
    rec = zone.get(domain)
    if not rec:
        return []
    out = []
    for x in rec.get("a", []):
        try:
            out.append(parse_ip(x))
        except ValueError:
            pass
    return out


def mx_ips(zone, domain):
    rec = zone.get(domain)
    if not rec:
        return []
    out = []
    for host in rec.get("mx", []):
        out.extend(a_records(zone, host))
    return out


def sanctioned_set(zone, domain):
    s = set(a_records(zone, domain))
    s.update(mx_ips(zone, domain))
    return s


class Budget:
    __slots__ = ("n",)

    def __init__(self):
        self.n = 0

    def charge(self):
        self.n += 1
        if self.n > LOOKUP_LIMIT:
            raise PermError("lookup limit")


# ---------------------------------------------------------------------------
# The evaluator. Returns (result, decisive_token_or_None).
# ---------------------------------------------------------------------------
def _eval(zone, current, request, ip, budget, faults, depth):
    if depth > MAX_DELEGATION:
        return ("PERMERROR", None)
    rec = zone.get(current)
    if not rec or "sap" not in rec:
        return ("NONE", None)
    try:
        pol = parse_policy(rec["sap"])
    except PermError:
        return ("PERMERROR", None)

    settled = None
    for t in pol.directives:
        if t.mech == "all":
            matched = True
        elif t.mech == "ip4":
            net, prefix = t.cidr
            matched = cidr_contains(ip, net, prefix, faults)
        elif t.mech in ("a", "mx"):
            budget.charge()
            target = t.arg if t.arg is not None else request
            ips = a_records(zone, target) if t.mech == "a" else mx_ips(zone, target)
            matched = ip in ips
        elif t.mech == "include":
            budget.charge()
            r, _ = _eval(zone, t.arg, request, ip, budget, faults, depth + 1)
            if r == "PERMERROR":
                return ("PERMERROR", None)
            matched = r == "PASS"
        else:
            matched = False
        if matched:
            settled = (QMAP[t.qual], t.raw)
            if F_LAST not in faults:
                return settled

    if settled is not None:
        return settled

    if pol.redirect is not None and not pol.has_all:
        if F_BUDGET not in faults:
            budget.charge()
        sub = pol.redirect if F_REQ in faults else request
        r, tok = _eval(zone, pol.redirect, sub, ip, budget, faults, depth + 1)
        if r == "NONE":
            return ("PERMERROR", None)
        return (r, tok)
    return ("NEUTRAL", None)


def decide(zone, domain, ip, faults):
    """(result, decisive_token_or_None) under the given fault set."""
    try:
        return _eval(zone, domain, domain, ip, Budget(), faults, 0)
    except PermError:
        return ("PERMERROR", None)


def verdict(zone, domain, ip, faults):
    return decide(zone, domain, ip, faults)[0]


def point_result(zone, domain, ip):
    """The intended result, per docs/sap-spec.md Part 1."""
    return verdict(zone, domain, ip, frozenset())


def witness_token(zone, domain, ip, deployed, intended):
    """The decisive token reported for a divergent query, per spec Part 2.

    Total by construction: drawn from whichever side authorizes the sender, from
    the deployed side when neither does, and "-" when that side was not settled
    by a directive.
    """
    if deployed == "PASS":
        side = ALL_FAULTS
    elif intended == "PASS":
        side = frozenset()
    else:
        side = ALL_FAULTS
    tok = decide(zone, domain, ip, side)[1]
    return tok if tok is not None else "-"


def analyze_point(zone, domain, ip):
    dep = verdict(zone, domain, ip, ALL_FAULTS)
    intd = verdict(zone, domain, ip, frozenset())
    solo = {f: verdict(zone, domain, ip, frozenset({f})) for f in ALL_FAULTS}
    divergent = dep != intd
    return {
        "deployed": dep,
        "intended": intd,
        "divergent": divergent,
        "witness": witness_token(zone, domain, ip, dep, intd) if divergent else None,
        # Which single faults, on their own, already account for the deployed
        # result. Empty on an interaction query: only the joint model explains it.
        "classes": sorted(f for f in ALL_FAULTS if divergent and solo[f] == dep),
        "interaction": divergent and all(v != dep for v in solo.values()),
        "cancelling": (not divergent) and any(v != intd for v in solo.values()),
    }


def analyze_case(case):
    zone = case["zone"]
    out = []
    for q in case["queries"]:
        ip = parse_ip(q["ip"])
        r = analyze_point(zone, q["domain"], ip)
        r["id"] = q["id"]
        out.append(r)
    return {"queries": out}
