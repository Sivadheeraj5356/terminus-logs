"""Reference audit engine + evidence-corpus generator for the grid revenue-protection case.

Independent implementation of the whole audit: the rules come from the milestone instructions,
the layouts from /app/spec/FORMATS.md. Also seeds the hidden evidence corpora the verifier
grades against.

The audit is NOT per-account decomposable. Admission is bounded by the minimum residual
along an account's WHOLE ancestor chain and depletes every ancestor; the progressive bands
are indexed by the SUPPLY POINT's shared running cumulative; draws settle in a live-keyed
order re-derived after every settlement; and the condemnation cascade closes to a fixpoint
that severs accounts with nothing locally wrong.
"""

import json
import os
import random
import struct

FNV_BASIS = 0x811C9DC5
FNV_PRIME = 0x01000193

SOURCES = ["telemetry", "estimate", "manual"]
SRC_RANK = {"telemetry": 0, "estimate": 1, "manual": 2}
KINDS = ["tamper", "spoliation", "misdeclare", "replay", "bypass", "quarantine",
         "void_fraud", "condemnation"]
PEAK_WINDOWS = [(7 * 3600, 10 * 3600), (17 * 3600, 20 * 3600)]
CATEGORIES = ["residential", "commercial", "industrial"]


def fnv1a(data):
    h = FNV_BASIS
    for b in data:
        h ^= b
        h = (h * FNV_PRIME) & 0xFFFFFFFF
    return "%08x" % h


def jdump(obj):
    return json.dumps(obj, separators=(",", ":"))


def _swap(byte):
    return ((byte << 4) & 0xF0) | ((byte >> 4) & 0x0F)


def checksum(buf):
    acc = 0
    i = 0
    n = len(buf)
    while i < n:
        hi = buf[i]
        lo = buf[i + 1] if i + 1 < n else 0
        acc ^= (hi << 8) | lo
        i += 2
    return (_swap((acc >> 8) & 0xFF) << 8) | _swap(acc & 0xFF)


# ---------------------------------------------------------------- registry

class Reg:
    def __init__(self, raw):
        self.raw = raw
        self.utilities = {u["id"]: u for u in raw["utilities"]}
        self.util_by_code = {u["code"]: u["id"] for u in raw["utilities"]}
        self.feeders = {f["id"]: f for f in raw["feeders"]}
        self.points = {p["id"]: p for p in raw["points"]}
        self.point_by_code = {p["code"]: p["id"] for p in raw["points"]}
        self.accounts = {a["id"]: a for a in raw["accounts"]}
        self.acct_by_code = {a["code"]: a["id"] for a in raw["accounts"]}
        self.acct_by_serial = {a["serial"]: a["id"] for a in raw["accounts"]}
        self.bands = raw["bands"]
        self.standing = raw["standing"]
        self.shed = raw["shed"]
        self.condemn_threshold = raw["condemn_threshold"]
        self.penalty_cents = raw["penalty_cents"]
        self.replay_window_sec = raw["replay_window_sec"]
        self.transfer = {}
        for t in raw["transfer"]:
            self.transfer[(t["a"], t["b"])] = t["min_sec"]
            self.transfer[(t["b"], t["a"])] = t["min_sec"]
        self._chain = {}
        self._kids = {a: [] for a in self.accounts}
        for a in raw["accounts"]:
            if a.get("parent"):
                self._kids[a["parent"]].append(a["id"])

    @staticmethod
    def home(acct):
        return acct.split("-")[0]

    def chain(self, acct):
        if acct in self._chain:
            return self._chain[acct]
        out = []
        cur = acct
        seen = set()
        while cur is not None and cur not in seen:
            seen.add(cur)
            out.append(cur)
            cur = self.accounts[cur].get("parent")
        self._chain[acct] = out
        return out

    def root(self, acct):
        return self.chain(acct)[-1]

    def subtree(self, acct):
        out = [acct]
        i = 0
        while i < len(out):
            out.extend(self._kids.get(out[i], []))
            i += 1
        return out


# ---------------------------------------------------------------- segment codec

def encode_record(acct_code, point_code, util_code, ts_off, source, claimed, inspect,
                  serial, kwh, stamp, corrupt=False):
    flags = (source & 0x03) | ((claimed & 0x07) << 2) | ((1 if inspect else 0) << 5)
    sb = serial.encode() if serial else b""
    body = struct.pack("<I", acct_code) + struct.pack(">H", point_code)
    body += struct.pack("<H", util_code) + struct.pack("<I", ts_off)
    body += bytes([flags, len(sb)]) + sb
    body += struct.pack(">H", kwh) + struct.pack(">H", stamp) + b"\x00\x00"
    rec = body[:-2] + struct.pack(">H", checksum(body))
    if corrupt:
        b = bytearray(rec)
        b[8] ^= 0x40
        rec = bytes(b)
    return rec


def encode_segment(count, base, stamp, records, truncate_bytes=0):
    head = b"MEX1" + struct.pack(">H", count) + struct.pack("<I", base)
    head += struct.pack(">H", stamp) + b"\x00\x00"
    head = head[:-2] + struct.pack(">H", checksum(head))
    body = b"".join(records)
    if truncate_bytes:
        body = body[:len(body) - truncate_bytes]
    return head + body


def parse_segment(buf):
    if len(buf) < 14 or buf[0:4] != b"MEX1":
        return None, [], 0
    count = struct.unpack(">H", buf[4:6])[0]
    base = struct.unpack("<I", buf[6:10])[0]
    off = 14
    recs = []
    while len(recs) < count:
        if off + 14 > len(buf):
            break
        slen = buf[off + 13]
        total = 20 + slen
        if off + total > len(buf):
            break
        raw = buf[off:off + total]
        stored = struct.unpack(">H", raw[-2:])[0]
        ok = checksum(raw[:-2] + b"\x00\x00") == stored
        r = {"ordinal": len(recs), "ok": ok}
        if ok:
            r["acct_code"] = struct.unpack("<I", raw[0:4])[0]
            r["point_code"] = struct.unpack(">H", raw[4:6])[0]
            r["util_code"] = struct.unpack("<H", raw[6:8])[0]
            r["ts"] = base + struct.unpack("<I", raw[8:12])[0]
            fl = raw[12]
            r["source"] = SOURCES[fl & 0x03] if (fl & 0x03) < 3 else "manual"
            r["claimed"] = (fl >> 2) & 0x07
            r["inspect"] = bool((fl >> 5) & 1)
            r["serial"] = raw[14:14 + slen].decode("ascii", "replace")
            r["kwh"] = struct.unpack(">H", raw[14 + slen:16 + slen])[0]
        recs.append(r)
        off += total
    ucode = None
    for r in recs:
        if r["ok"]:
            ucode = r["util_code"]
            break
    return ucode, recs, count - len(recs)


# ---------------------------------------------------------------- circulars

def parse_circular(text):
    lines = text.split("\n")
    head = {}
    i = 1
    while i < len(lines):
        ln = lines[i]
        if not ln.strip() or ":" not in ln:
            break
        k, v = ln.split(":", 1)
        if k != k.strip() or not k.replace("-", "").isalpha() or not k.isupper():
            break
        head[k.strip()] = v.strip()
        i += 1
    directives = []
    inblock = False
    for ln in lines:
        s = ln.strip()
        if s == "DIRECTIVES:":
            inblock = True
            continue
        if s == "END DIRECTIVES":
            inblock = False
            continue
        if inblock and s:
            directives.append(s)
    eff = head.get("EFFECTIVE", "0")
    if " TO " in eff:
        a, b = eff.split(" TO ")
        start, end = int(a.strip()), int(b.strip())
    else:
        start, end = int(eff.strip()), None
    sup = [x.strip() for x in head.get("SUPERSEDES", "").split(",") if x.strip()]
    return {"ref": head["REF"], "issuer": head["ISSUER"], "issued": int(head["ISSUED"]),
            "start": start, "end": end, "supersedes": sup, "directives": directives}


def dead_refs(circs):
    byref = {c["ref"]: c for c in circs}
    dead = set()
    for c in circs:
        for target in c["supersedes"]:
            t = byref.get(target)
            if t is None:
                continue
            if c["issuer"] == "REGULATOR" or c["issuer"] == t["issuer"]:
                dead.add(target)
    return dead


def _in_force(c, t):
    if c["end"] is None:
        return t >= c["start"]
    return c["start"] <= t < c["end"]


def _outranks(a, spec_a, b, spec_b):
    if spec_a != spec_b:
        return spec_a > spec_b
    ra = 1 if a["issuer"] == "REGULATOR" else 0
    rb = 1 if b["issuer"] == "REGULATOR" else 0
    if ra != rb:
        return ra > rb
    if a["start"] != b["start"]:
        return a["start"] > b["start"]
    if a["issued"] != b["issued"]:
        return a["issued"] > b["issued"]
    return a["ref"] > b["ref"]


class Policy:
    def __init__(self, reg, circs):
        self.reg = reg
        self.all = {c["ref"]: c for c in circs}
        self.dead = dead_refs(circs)
        self.live = [c for c in circs if c["ref"] not in self.dead]

    def _pick(self, t, match):
        best = None
        bspec = -1
        for c in self.live:
            if not _in_force(c, t):
                continue
            for d in c["directives"]:
                got = match(d)
                if got is None:
                    continue
                spec, val = got
                if best is None or _outranks(c, spec, best[0], bspec):
                    best, bspec = (c, val), spec
        return None if best is None else best[1]

    def bands(self, root, t):
        def m(d):
            p = d.split()
            if p[0] != "BANDS" or len(p) < 3:
                return None
            if p[1] == root:
                spec = 1
            elif p[1] == "ALL":
                spec = 0
            else:
                return None
            rows = []
            for tok in p[2:]:
                a, b = tok.split(":")
                rows.append({"from_kwh": int(a), "rate_cents": int(b)})
            return spec, rows
        v = self._pick(t, m)
        return v if v is not None else self.reg.bands

    def standing(self, category, t):
        def m(d):
            p = d.split()
            if p[0] != "STANDING" or len(p) < 3 or p[1] != category:
                return None
            tbl = {}
            for tok in p[2:]:
                a, b = tok.split(":")
                tbl[a] = int(b)
            return 0, tbl
        v = self._pick(t, m)
        return v if v is not None else self.reg.standing[category]

    def shed(self, root, t):
        def m(d):
            p = d.split()
            if p[0] != "SHED" or len(p) < 8 or p[1] != root:
                return None
            return 0, {"window_draws": int(p[3]), "enter_kwh": int(p[5]),
                       "exit_kwh": int(p[7])}
        v = self._pick(t, m)
        return v if v is not None else self.reg.shed

    def exempt(self, acct, t):
        for c in self.live:
            if not _in_force(c, t):
                continue
            for d in c["directives"]:
                p = d.split()
                if p[0] == "EXEMPT" and len(p) >= 2 and p[1] == acct:
                    return True
        return False

    def basis_state(self, ref, t):
        if ref not in self.all:
            return "unknown"
        if ref in self.dead:
            return "superseded"
        if not _in_force(self.all[ref], t):
            return "expired"
        return "ok"


# ---------------------------------------------------------------- stage 1: intake

def face_cents(reg, point, acct, kwh):
    cat = reg.points[point]["category"]
    cls = str(reg.accounts[acct]["class"])
    return kwh * reg.bands[0]["rate_cents"] + reg.standing[cat][cls]


def intake(reg, segs):
    evidence = []
    findings = {k: [] for k in KINDS}
    stats = {u: {"reads": 0, "tamper": 0, "lost": 0, "misdeclare": 0, "flagged": 0}
             for u in reg.utilities}
    unresolved = 0
    nrecords = 0
    for name, buf in segs:
        ucode, recs, lost = parse_segment(buf)
        util = reg.util_by_code.get(ucode, "")
        nrecords += len(recs)
        for r in recs:
            if not r["ok"]:
                if util:
                    stats[util]["tamper"] += 1
                findings["tamper"].append({"kind": "tamper", "utility": util,
                                           "segment": name, "record": r["ordinal"],
                                           "cents": reg.penalty_cents})
                continue
            rutil = reg.util_by_code.get(r["util_code"], "")
            if rutil:
                stats[rutil]["reads"] += 1
                if r["inspect"]:
                    stats[rutil]["flagged"] += 1
            if r["source"] == "telemetry":
                acct = reg.acct_by_code.get(r["acct_code"])
            else:
                acct = reg.acct_by_serial.get(r["serial"])
            point = reg.point_by_code.get(r["point_code"])
            if acct is None or point is None:
                unresolved += 1
                continue
            cat = reg.points[point]["category"]
            rclass = reg.accounts[acct]["class"]
            if r["claimed"] != rclass:
                base_r = reg.standing[cat][str(rclass)]
                base_c = reg.standing[cat].get(str(r["claimed"]), 0)
                if r["claimed"] < 1 or r["claimed"] > 4:
                    base_c = 0
                if rutil:
                    stats[rutil]["misdeclare"] += 1
                findings["misdeclare"].append(
                    {"kind": "misdeclare", "utility": rutil, "segment": name,
                     "record": r["ordinal"], "account": acct, "claimed": r["claimed"],
                     "registry": rclass, "cents": max(0, base_r - base_c)})
            evidence.append({"segment": name, "record": r["ordinal"], "utility": rutil,
                             "account": acct, "point": point, "ts": r["ts"],
                             "source": r["source"], "class": r["claimed"],
                             "kwh": r["kwh"], "inspect": r["inspect"]})
        if lost > 0:
            if util:
                stats[util]["lost"] += lost
            findings["spoliation"].append({"kind": "spoliation", "utility": util,
                                           "segment": name, "lost": lost,
                                           "cents": lost * reg.penalty_cents})
    evidence.sort(key=lambda e: (e["segment"], e["record"]))
    return evidence, findings, stats, unresolved, nrecords


# ---------------------------------------------------------------- stage 2: draws

def _fold(reg, point, acct, rs):
    owner = reg.points[point]["utility"]
    best = min(rs, key=lambda e: (SRC_RANK[e["source"]],
                                  0 if e["utility"] == owner else 1,
                                  e["ts"], e["utility"]))
    return {"id": "%s:%s:%d" % (acct, point, best["ts"]), "ts": best["ts"],
            "point": point, "operator": owner, "feeder": reg.points[point]["feeder"],
            "account": acct, "home": Reg.home(acct), "root": reg.root(acct),
            "class": reg.accounts[acct]["class"], "source": best["source"],
            "reads": len(rs), "kwh": best["kwh"], "status": "ok"}


def reconstruct(reg, evidence):
    groups = {}
    for e in evidence:
        groups.setdefault((e["point"], e["account"]), []).append(e)
    draws = []
    for (point, acct), rs in groups.items():
        rs.sort(key=lambda e: (e["ts"], SRC_RANK[e["source"]], e["utility"]))
        cur = []
        for e in rs:
            if cur and e["ts"] - cur[0]["ts"] <= 5:
                cur.append(e)
            else:
                if cur:
                    draws.append(_fold(reg, point, acct, cur))
                cur = [e]
        if cur:
            draws.append(_fold(reg, point, acct, cur))
    draws.sort(key=lambda d: (d["ts"], d["point"], d["account"]))
    return draws


def detect(reg, draws, findings):
    last = {}
    rep = {}
    for d in draws:
        key = (d["point"], d["account"])
        prev = last.get(key)
        if prev is not None and d["ts"] - prev["ts"] < reg.replay_window_sec:
            d["status"] = "replay"
            rep[d["id"]] = (prev["id"], d["ts"] - prev["ts"])
        else:
            last[key] = d
    by_acct = {}
    for d in draws:
        by_acct.setdefault(d["account"], []).append(d)
    byp = {}
    for acct in by_acct:
        accepted = None
        for d in by_acct[acct]:
            if d["status"] == "replay":
                continue
            if accepted is not None and d["point"] != accepted["point"]:
                bound = reg.transfer.get((accepted["point"], d["point"]))
                gap = d["ts"] - accepted["ts"]
                if bound is not None and gap < bound:
                    d["status"] = "bypass"
                    byp[d["id"]] = (accepted["id"], gap, bound)
                    continue
            accepted = d
    # replay and bypass findings are emitted in the flagged draw's REGISTER order
    for d in draws:
        if d["status"] == "replay":
            prior, gap = rep[d["id"]]
            findings["replay"].append(
                {"kind": "replay", "account": d["account"], "home": d["home"],
                 "draw": d["id"], "prior": prior, "gap_sec": gap,
                 "cents": face_cents(reg, d["point"], d["account"], d["kwh"])})
    for d in draws:
        if d["status"] == "bypass":
            conflict, gap, bound = byp[d["id"]]
            findings["bypass"].append(
                {"kind": "bypass", "account": d["account"], "home": d["home"],
                 "draw": d["id"], "conflict": conflict, "gap_sec": gap,
                 "bound_sec": bound,
                 "cents": face_cents(reg, d["point"], d["account"], d["kwh"])})
    for acct in sorted(by_acct):
        ds = by_acct[acct]
        first = None
        for d in ds:
            if d["status"] == "bypass":
                first = d["ts"]
                break
        if first is None:
            continue
        suspects = []
        for d in ds:
            if d["ts"] >= first and d["status"] == "ok":
                d["status"] = "suspect"
                suspects.append(d)
        findings["quarantine"].append(
            {"kind": "quarantine", "account": acct, "home": Reg.home(acct),
             "from_ts": first, "draws": len(suspects),
             "cents": sum(face_cents(reg, s["point"], acct, s["kwh"])
                          for s in suspects)})
    return draws


# ---------------------------------------------------------------- stage 3: settle

def _peak(ts, off_min):
    t = (ts + off_min * 60) % 86400
    return any(a <= t < b for a, b in PEAK_WINDOWS)


def _energy(bands, start, end):
    cost = 0
    for i, b in enumerate(bands):
        lo = b["from_kwh"]
        hi = bands[i + 1]["from_kwh"] if i + 1 < len(bands) else None
        a = max(start, lo)
        z = end if hi is None else min(end, hi)
        if z > a:
            cost += (z - a) * b["rate_cents"]
    return cost


def _rolling(slots, window):
    take = slots[-window:] if window > 0 else []
    return sum(k * (2 if s else 1) for k, s in take)


def _headroom(reg, drawn, acct, v):
    if v.get("own_residual"):
        return max(0, reg.accounts[acct]["allowance_kwh"] - drawn[acct])
    best = None
    for n in reg.chain(acct):
        r = reg.accounts[n]["allowance_kwh"] - drawn[n]
        if best is None or r < best:
            best = r
    return max(0, best)


def settle(reg, pol, draws, statuses, variant=None):
    v = variant or {}
    drawn = {a: 0 for a in reg.accounts}
    root_cum = {}
    acct_cum = {}
    shed_on = {}
    slots = {}
    remaining = list(draws)
    rows = []
    while remaining:
        if v.get("fixed_sort"):
            d = min(remaining, key=lambda x: (x["ts"], x["point"], x["account"]))
            hr = _headroom(reg, drawn, d["account"], v)
        else:
            best = None
            for x in remaining:
                h = _headroom(reg, drawn, x["account"], v)
                k = (h, x["ts"], x["point"], x["account"])
                if best is None or k < best[0]:
                    best = (k, x, h)
            d, hr = best[1], best[2]
        remaining.remove(d)
        root, t = d["root"], d["ts"]
        bands = pol.bands(root, t)
        cat = reg.points[d["point"]]["category"]
        stand_tbl = pol.standing(cat, t)
        sh = pol.shed(root, t)
        exempt = pol.exempt(d["account"], t)
        slots.setdefault(root, [])
        shed_on.setdefault(root, False)
        root_cum.setdefault(root, 0)
        acct_cum.setdefault(d["account"], 0)
        if shed_on[root] and _rolling(slots[root], sh["window_draws"]) < sh["exit_kwh"]:
            shed_on[root] = False
        in_shed = shed_on[root] and not exempt
        admitted = d["kwh"] if v.get("own_amount") else min(d["kwh"], hr)
        start = acct_cum[d["account"]] if v.get("per_account_bands") else root_cum[root]
        end = start + admitted
        toll = _energy(bands, start, end) + stand_tbl[str(d["class"])]
        standing = stand_tbl[str(d["class"])]
        peak = _peak(t, reg.utilities[d["operator"]]["utc_offset_min"])
        if peak:
            toll = toll * 5 // 4
        if in_shed:
            toll = toll * 3 // 2
        status = statuses[d["id"]]
        if status != "ok":
            charged = 0
            slots[root].append((0, False))
        else:
            charged = toll
            for n in reg.chain(d["account"]):
                drawn[n] += admitted
            root_cum[root] = end
            acct_cum[d["account"]] = end
            slots[root].append((admitted, in_shed))
        if not shed_on[root] and _rolling(slots[root], sh["window_draws"]) >= sh["enter_kwh"]:
            shed_on[root] = True
        rows.append({"id": d["id"], "ts": t, "point": d["point"],
                     "operator": d["operator"], "feeder": d["feeder"],
                     "account": d["account"], "home": d["home"], "root": root,
                     "class": d["class"], "source": d["source"], "reads": d["reads"],
                     "peak": peak, "shed": in_shed, "kwh": d["kwh"],
                     "admitted": admitted, "cum_start": start, "cum_end": end,
                     "standing_cents": standing, "toll_cents": toll,
                     "charged_cents": charged, "status": status})
    rows.sort(key=lambda r: (r["ts"], r["point"], r["account"]))
    return rows


def adjudicate(pol, draws, disputes):
    byid = {d["id"]: d for d in draws}
    voided = set()
    frauds = []
    for dp in sorted(disputes, key=lambda x: x["id"]):
        if dp["ruling"] != "upheld":
            continue
        d = byid.get(dp["draw"])
        if d is None:
            continue
        state = pol.basis_state(dp["basis"], d["ts"])
        if state == "ok":
            voided.add(dp["draw"])
        else:
            frauds.append({"kind": "void_fraud", "dispute": dp["id"],
                           "filed_by": dp["filed_by"], "draw": dp["draw"],
                           "basis": dp["basis"], "cause": state, "cents": 0})
    return voided, frauds


def _statuses(reg, draws, voided, condemned):
    st = {}
    for d in draws:
        if d["status"] != "ok":
            st[d["id"]] = d["status"]
        elif d["id"] in voided:
            st[d["id"]] = "voided"
        elif d["account"] in condemned:
            st[d["id"]] = "severed"
        else:
            st[d["id"]] = "ok"
    return st


def condemn_fixpoint(reg, draws, voided, variant=None):
    """Feeders lock out on OWN-EVIDENCE exclusions (replay, bypass, suspect, voided);
    severance is a consequence and never counts toward a threshold. The lockout then
    propagates through the supply chain to a fixpoint."""
    v = variant or {}
    base = _statuses(reg, draws, voided, set())
    excl = {}
    for d in draws:
        if base[d["id"]] != "ok":
            excl[d["feeder"]] = excl.get(d["feeder"], 0) + 1
    feeders = {f for f, n in excl.items() if n >= reg.condemn_threshold}
    if v.get("no_condemn"):
        return set(), feeders, _statuses(reg, draws, voided, set()), 1
    by_acct = {}
    for d in draws:
        by_acct.setdefault(d["account"], set()).add(d["feeder"])
    kids = {a: list(reg._kids.get(a, [])) for a in reg.accounts}
    condemned = set()
    hops = 0
    while True:
        grown = set(condemned)
        for acct, fs in by_acct.items():
            if fs and fs <= feeders:
                grown.add(acct)
        if not v.get("no_subtree"):
            for acct in list(grown):
                grown.update(reg.subtree(acct))
        if not v.get("no_upward"):
            for acct in sorted(reg.accounts):
                ch = kids[acct]
                if not ch or acct in grown:
                    continue
                if all(c in grown for c in ch):
                    grown.add(acct)
        hops += 1
        if v.get("one_pass"):
            return grown, feeders, _statuses(reg, draws, voided, grown), hops
        if grown == condemned:
            return condemned, feeders, _statuses(reg, draws, voided, condemned), hops
        condemned = grown


# ---------------------------------------------------------------- full audit

def audit(reg, segs, circs, disputes, stage=3, variant=None):
    v = variant or {}
    evidence, findings, stats, unresolved, nrecords = intake(reg, segs)
    out = {"evidence": evidence, "findings": findings, "stats": stats,
           "unresolved": unresolved, "records": nrecords, "segments": len(segs)}
    if stage == 1:
        return out
    draws = reconstruct(reg, evidence)
    detect(reg, draws, findings)
    out["draws"] = draws
    if stage == 2:
        return out
    pol = Policy(reg, circs)
    voided, frauds = adjudicate(pol, draws, disputes)
    condemned, cfeeders, statuses, hops = condemn_fixpoint(reg, draws, voided, v)
    if v.get("forward_void"):
        st2 = {k: ("ok" if s == "voided" else s) for k, s in statuses.items()}
        register = settle(reg, pol, draws, st2, v)
        for r in register:
            if statuses[r["id"]] == "voided":
                r["status"] = "voided"
                r["charged_cents"] = 0
    else:
        register = settle(reg, pol, draws, statuses, v)
    byid = {r["id"]: r for r in register}
    for fr in frauds:
        fr["cents"] = byid[fr["draw"]]["charged_cents"]
    findings["void_fraud"] = frauds
    for f in sorted(cfeeders):
        rws = [r for r in register if r["feeder"] == f]
        sev = [r for r in rws if r["status"] == "severed"]
        findings["condemnation"].append(
            {"kind": "condemnation", "feeder": f, "utility": reg.feeders[f]["utility"],
             "excluded": sum(1 for r in rws if r["status"] != "ok"),
             "severed": len(sev),
             "cents": sum(face_cents(reg, r["point"], r["account"], r["kwh"])
                          for r in sev)})
    out.update({"register": register, "condemned": sorted(condemned),
                "cfeeders": sorted(cfeeders), "voided": voided, "hops": hops})
    return out


# ---------------------------------------------------------------- emission

REG_KEYS = ["id", "ts", "point", "operator", "feeder", "account", "home", "root",
            "class", "source", "reads", "peak", "shed", "kwh", "admitted",
            "standing_cents", "toll_cents", "charged_cents", "status"]
DRAW_KEYS = ["id", "ts", "point", "operator", "feeder", "account", "home", "class",
             "source", "reads", "kwh", "status"]


def order_findings(f):
    rows = []
    rows += sorted(f["tamper"], key=lambda x: (x["segment"], x["record"]))
    rows += sorted(f["spoliation"], key=lambda x: x["segment"])
    rows += sorted(f["misdeclare"], key=lambda x: (x["segment"], x["record"]))
    rows += f["replay"]
    rows += f["bypass"]
    rows += sorted(f["quarantine"], key=lambda x: x["account"])
    rows += sorted(f["void_fraud"], key=lambda x: x["dispute"])
    rows += sorted(f["condemnation"], key=lambda x: x["feeder"])
    return rows


def findings_text(f):
    return "".join(jdump(r) + "\n" for r in order_findings(f))


def evidence_text(ev):
    return "".join(jdump(e) + "\n" for e in ev)


def draws_text(ds):
    return "".join(jdump({k: d[k] for k in DRAW_KEYS}) + "\n" for d in ds)


def register_text(rows):
    return "".join(jdump({k: r[k] for k in REG_KEYS}) + "\n" for r in rows)


def audit_text(rows):
    srt = sorted(rows, key=lambda r: (r["account"], r["ts"], r["point"]))
    return "".join(jdump({k: r[k] for k in REG_KEYS}) + "\n" for r in srt)


def kind_counts(f):
    return {k: len(f[k]) for k in KINDS}


def intake_json(reg, res):
    f = res["findings"]
    us = []
    for u in sorted(reg.utilities):
        s = res["stats"][u]
        leak = sum(x["cents"] for x in f["misdeclare"] if x["utility"] == u)
        us.append({"utility": u, "reads": s["reads"], "tamper": s["tamper"],
                   "lost": s["lost"], "misdeclare": s["misdeclare"],
                   "flagged": s["flagged"], "leakage_cents": leak,
                   "exposure_cents": leak + reg.penalty_cents * (s["tamper"] + s["lost"])})
    us.sort(key=lambda x: (-x["exposure_cents"], x["utility"]))
    kc = kind_counts(f)
    three = {k: kc[k] for k in KINDS[:3]}
    return {"segments": res["segments"], "records": res["records"],
            "reads": sum(s["reads"] for s in res["stats"].values()),
            "tampered": sum(s["tamper"] for s in res["stats"].values()),
            "lost": sum(s["lost"] for s in res["stats"].values()),
            "unresolved": res["unresolved"], "findings": sum(three.values()),
            "findings_by_kind": three, "utilities": us,
            "evidence_digest": fnv1a(evidence_text(res["evidence"]).encode()),
            "findings_digest": fnv1a(findings_text(f).encode())}


def draws_json(reg, res):
    d = res["draws"]
    f = res["findings"]
    bs = {s: sum(1 for x in d if x["status"] == s)
          for s in ["ok", "replay", "bypass", "suspect"]}
    kc = kind_counts(f)
    six = {k: kc[k] for k in KINDS[:6]}
    return {"draws": len(d), "excluded": sum(1 for x in d if x["status"] != "ok"),
            "by_status": bs,
            "compromised_accounts": sorted(x["account"] for x in f["quarantine"]),
            "findings": sum(six.values()), "findings_by_kind": six,
            "draws_digest": fnv1a(draws_text(d).encode()),
            "findings_digest": fnv1a(findings_text(f).encode())}


def summary_json(reg, res):
    rows = res["register"]
    f = res["findings"]
    kc = kind_counts(f)
    stats = res["stats"]
    exposure = []
    for u in sorted(reg.utilities):
        s = stats[u]
        cnt = lambda st: sum(1 for r in rows if r["status"] == st and r["home"] == u)  # noqa: E731
        leak = sum(x["cents"] for x in f["misdeclare"] if x["utility"] == u)
        leak += sum(x["cents"] for x in f["replay"] if x["home"] == u)
        leak += sum(x["cents"] for x in f["bypass"] if x["home"] == u)
        leak += sum(x["cents"] for x in f["quarantine"] if x["home"] == u)
        leak += sum(x["cents"] for x in f["void_fraud"] if x["filed_by"] == u)
        leak += sum(x["cents"] for x in f["condemnation"] if x["utility"] == u)
        exposure.append({
            "utility": u, "reads": s["reads"], "tamper": s["tamper"], "lost": s["lost"],
            "misdeclare": s["misdeclare"], "flagged": s["flagged"],
            "replay": cnt("replay"), "bypass": cnt("bypass"), "suspect": cnt("suspect"),
            "severed": cnt("severed"),
            "void_fraud": sum(1 for x in f["void_fraud"] if x["filed_by"] == u),
            "condemned_feeders": sum(1 for x in f["condemnation"] if x["utility"] == u),
            "leakage_cents": leak,
            "exposure_cents": leak + reg.penalty_cents * (s["tamper"] + s["lost"])})
    exposure.sort(key=lambda x: (-x["exposure_cents"], x["utility"]))
    roots = {}
    for r in rows:
        roots.setdefault(r["root"], []).append(r)
    supply = []
    for root in sorted(roots):
        rws = roots[root]
        ok = [r for r in rws if r["status"] == "ok"]
        if not ok:
            continue
        adm = sum(r["admitted"] for r in ok)
        supply.append({"root": root, "utility": Reg.home(root),
                       "accounts": len({r["account"] for r in rws}), "draws": len(rws),
                       "admitted_kwh": adm,
                       "charged_cents": sum(r["charged_cents"] for r in ok),
                       "shed_draws": sum(1 for r in rws if r["shed"]),
                       "final_headroom": max(
                           0, reg.accounts[root]["allowance_kwh"] - adm)})
    case = {"draws": len(rows),
            "excluded": sum(1 for r in rows if r["status"] != "ok"),
            "reads": sum(s["reads"] for s in stats.values()),
            "tampered": sum(s["tamper"] for s in stats.values()),
            "lost": sum(s["lost"] for s in stats.values()),
            "findings": sum(kc.values()), "findings_by_kind": kc,
            "compromised_accounts": sorted(x["account"] for x in f["quarantine"]),
            "condemned_feeders": res["cfeeders"],
            "severed_accounts": res["condemned"],
            "charged_cents": sum(r["charged_cents"] for r in rows),
            "leakage_cents": sum(x["leakage_cents"] for x in exposure),
            "exposure_cents": sum(x["exposure_cents"] for x in exposure),
            "top_utility": exposure[0]["utility"] if exposure else ""}
    return {"case": case, "exposure": exposure, "supply": supply,
            "register_digest": fnv1a(register_text(rows).encode()),
            "audit_digest": fnv1a(audit_text(rows).encode()),
            "findings_digest": fnv1a(findings_text(f).encode())}


# ---------------------------------------------------------------- corpus loading

def load_corpus(data_dir):
    with open(os.path.join(data_dir, "registry.json")) as f:
        reg = Reg(json.load(f))
    segs = []
    sd = os.path.join(data_dir, "exports")
    for name in sorted(os.listdir(sd)):
        with open(os.path.join(sd, name), "rb") as f:
            segs.append((name, f.read()))
    circs = []
    cd = os.path.join(data_dir, "circulars")
    if os.path.isdir(cd):
        for name in sorted(os.listdir(cd)):
            with open(os.path.join(cd, name)) as f:
                circs.append(parse_circular(f.read()))
    disputes = []
    dp = os.path.join(data_dir, "disputes.jsonl")
    if os.path.exists(dp):
        with open(dp) as f:
            for line in f:
                if line.strip():
                    disputes.append(json.loads(line))
    return reg, segs, circs, disputes


# ---------------------------------------------------------------- corpus generator

DAY = 1767225600  # 2026-01-01T00:00:00Z

NARRATIVE = [
    "The board notes that field inspections in the northern district recovered 41 tapped "
    "service heads last quarter, at an estimated 250 cents per kWh of unbilled energy.",
    "Members are reminded that figures quoted in the annexes of earlier circulars are "
    "indicative only and carry no operative force.",
    "A working group will report on whether the 3000 kWh threshold discussed in committee "
    "should be adopted; no change is made by this circular.",
    "Revenue protection staff report that estimate-sourced reads remain the most common "
    "vector for class understatement.",
    "The regulator restates that a directive block is the only operative content of a "
    "circular; narrative paragraphs bind nobody.",
]

KNOBS = {
    "events": 420, "feeders_per_util": 4, "points_per_feeder": 2, "spine": 7,
    "root_alw": 1400, "step_alw": 190,
    "condemn": 11, "fixed_p": 0.60, "hot_p": 0.20, "roam_p": 0.42, "roam_depth": 3,
    "replays": 9, "bypasses": 8, "misdeclares": 11, "corrupt": 8, "trunc": 5,
    "enter": 260, "exit": 80, "window": 5,
}


def _mk_circulars(rnd, roots, accounts, span):
    t0, t1 = span
    circs = []
    n = [0]

    def emit(issuer, issued, start, end, supersedes, directives, note=0):
        n[0] += 1
        ref = "GRP-26-%03d" % (100 + n[0])
        lines = ["GRID REVENUE PROTECTION CIRCULAR", "REF: " + ref,
                 "ISSUER: " + issuer, "ISSUED: %d" % issued]
        lines.append("EFFECTIVE: %d" % start if end is None
                     else "EFFECTIVE: %d TO %d" % (start, end))
        if supersedes:
            lines.append("SUPERSEDES: " + ", ".join(supersedes))
        lines.append("")
        lines.append(NARRATIVE[note % len(NARRATIVE)])
        lines.append("")
        if directives:
            lines.append("DIRECTIVES:")
            lines.extend(directives)
            lines.append("END DIRECTIVES")
            lines.append("")
        lines.append(NARRATIVE[(note + 2) % len(NARRATIVE)])
        lines.append("")
        circs.append((ref, "\n".join(lines)))
        return ref

    lo = t0 - 86400
    for i, r in enumerate(roots[:3]):
        emit(Reg.home(r), lo - 3600 * i, lo, None, [],
             ["BANDS %s 0:%d 90:%d 210:%d" % (r, 9 + i, 19 + i, 32 + i)], note=i)
    all_ref = emit("REGULATOR", lo - 7200, lo, None, [],
                   ["BANDS ALL 0:11 120:21 240:29"], note=1)
    old = emit(Reg.home(roots[0]), lo - 20000, lo, None, [],
               ["BANDS %s 0:40 50:60 100:90" % roots[0]], note=3)
    emit("REGULATOR", lo - 10000, lo, None, [old], [], note=4)
    exp = emit("REGULATOR", lo - 30000, lo - 20000, lo - 10000, [],
               ["STANDING commercial 1:900 2:950 3:990 4:1200"], note=2)
    emit("REGULATOR", lo - 5000, lo, None, [],
         ["STANDING industrial 1:400 2:460 3:520 4:600"], note=0)
    emit(Reg.home(roots[1]), lo - 4000, lo, None, [all_ref], [], note=1)
    for i, r in enumerate(roots[3:6]):
        emit("REGULATOR", lo - 2000 - i, lo, None, [],
             ["SHED %s WINDOW 4 ENTER %d EXIT %d" % (r, 150 + 20 * i, 55 + 5 * i)],
             note=i)
    ex = sorted(a for a in accounts if accounts[a].get("parent"))
    rnd.shuffle(ex)
    for i, a in enumerate(ex[:3]):
        emit(Reg.home(a), lo - 1500 - i, lo, None, [], ["EXEMPT " + a], note=i)
    for i in range(4):
        emit("REGULATOR" if i % 2 else Reg.home(roots[i % len(roots)]),
             lo - 900 - i, lo, None, [], [], note=i)
    return circs, exp, old


def make_corpus(seed, knobs=None):
    """Deterministically seed one evidence corpus.
    Returns (registry_raw, [(segname, bytes)], [(ref, text)], [disputes])."""
    K = dict(KNOBS)
    K.update(knobs or {})
    rnd = random.Random(seed)
    utils = ["NOR", "EAS", "WES"]
    utilities = [{"id": u, "utc_offset_min": off, "code": 9001 + i}
                 for i, (u, off) in enumerate(zip(utils, [60, -150, 330]))]
    feeders, points = [], []
    fcode, pcode = 401, 601
    for ui, u in enumerate(utils):
        for k in range(K["feeders_per_util"]):
            fid = "F-%s-%d" % (u, k + 1)
            feeders.append({"id": fid, "utility": u, "code": fcode})
            fcode += 1
            for j in range(K["points_per_feeder"]):
                points.append({"id": "D-%s-%d%d" % (u, k + 1, j + 1), "feeder": fid,
                               "utility": u,
                               "category": CATEGORIES[(ui + k + j) % 3], "code": pcode})
                pcode += 1
    # Account forest: per supply point a spine of holding accounts, each backing the
    # next holding account AND one retail sub-account. Every non-leaf backs exactly two
    # sub-accounts, so a lockout climbing the chain has to take out a whole level.
    accounts, roots = [], []
    depths = {}
    acode = 70001
    for ui, u in enumerate(utils):
        for tree in range(2):
            depth = K["spine"]
            spine = []
            for d in range(depth):
                aid = "%s-%d%d0" % (u, tree + 1, d)
                alw = K["root_alw"] - K["step_alw"] * d - 40 * tree
                accounts.append({"id": aid, "parent": spine[-1] if spine else None,
                                 "class": 1 + ((d + ui + tree) % 4),
                                 "allowance_kwh": max(200, alw), "code": acode,
                                 "serial": "SN" + aid.replace("-", "")})
                depths[aid] = d
                acode += 1
                spine.append(aid)
            roots.append(spine[0])
            for d in range(depth - 1):
                aid = "%s-%d%d1" % (u, tree + 1, d)
                accounts.append({"id": aid, "parent": spine[d],
                                 "class": 1 + ((d + ui) % 4),
                                 "allowance_kwh": max(200, 460 - 30 * d), "code": acode,
                                 "serial": "SN" + aid.replace("-", "")})
                depths[aid] = d + 1
                acode += 1
    accmap = {a["id"]: a for a in accounts}
    transfer = []
    for i in range(len(points)):
        for j in range(i + 1, len(points)):
            same = points[i]["feeder"] == points[j]["feeder"]
            transfer.append({"a": points[i]["id"], "b": points[j]["id"],
                             "min_sec": 900 if same else 2400})
    registry = {
        "utilities": utilities, "feeders": feeders, "points": points,
        "accounts": accounts,
        "bands": [{"from_kwh": 0, "rate_cents": 10},
                  {"from_kwh": 100, "rate_cents": 20},
                  {"from_kwh": 200, "rate_cents": 30}],
        "standing": {
            "residential": {"1": 100, "2": 150, "3": 220, "4": 300},
            "commercial": {"1": 800, "2": 880, "3": 960, "4": 1100},
            "industrial": {"1": 360, "2": 420, "3": 500, "4": 640}},
        "shed": {"window_draws": K["window"], "enter_kwh": K["enter"],
                 "exit_kwh": K["exit"]},
        "condemn_threshold": K["condemn"], "penalty_cents": 500,
        "replay_window_sec": 900, "transfer": transfer,
    }
    drawers = [a["id"] for a in accounts]
    pids = [p["id"] for p in points]
    fids = [f["id"] for f in feeders]
    hot_f = [fids[i] for i in (0, 3, 5, 9)]
    hot = [p["id"] for p in points if p["feeder"] in hot_f]
    primary, roams = {}, {}
    for a in drawers:
        primary[a] = rnd.choice(hot) if rnd.random() < K["hot_p"] else rnd.choice(pids)
        # holding accounts high in a chain are multi-site by nature; retail
        # sub-accounts sit on one delivery point
        roams[a] = (depths[a] <= K["roam_depth"]
                    or rnd.random() > K["fixed_p"])
    # deliberate plants: a mid-chain holding account whose entire metering sits on one
    # circuit (its lockout drags its whole subtree down), and a ladder of retail
    # sub-accounts that lets the lockout climb the chain level by level
    pinned = [
        # the showcase chain: a mid-chain holding account plus the retail sub-accounts
        # one and two levels above it, so the lockout climbs the chain level by level
        ("NOR-130", hot_f[0]), ("NOR-121", hot_f[0]), ("NOR-111", hot_f[1]),
        ("NOR-101", hot_f[1]),
        # elsewhere a single deep holding account whose subtree goes down with it
        ("EAS-240", hot_f[2]), ("WES-140", hot_f[3]),
    ]
    pin_pts = {}
    for aid, f in pinned:
        if aid in accmap:
            cands = [p["id"] for p in points if p["feeder"] == f]
            pin_pts[aid] = cands
            roams[aid] = False
            primary[aid] = cands[0]
    events = []
    t = DAY + 3600
    order = list(drawers)
    for i in range(K["events"]):
        a = order[i % len(order)] if i < 2 * len(order) else rnd.choice(drawers)
        p = rnd.choice(pin_pts[a]) if a in pin_pts else primary[a]
        if a not in pin_pts and roams[a] and rnd.random() < K["roam_p"]:
            p = rnd.choice(pids)
        t += rnd.randint(120, 1400)
        events.append({"acct": a, "point": p, "ts": t, "kwh": rnd.randint(6, 80),
                       "claimed": accmap[a]["class"],
                       "src": 0 if rnd.random() < 0.7 else rnd.choice([1, 2]),
                       "inspect": rnd.random() < 0.12})
    # The fraud is concentrated on the circuits under investigation.
    hot_events = [e for e in events if e["point"] in hot]
    for _ in range(K["replays"]):
        e = rnd.choice(hot_events)
        events.append(dict(e, ts=e["ts"] + rnd.randint(60, 800),
                           kwh=rnd.randint(6, 60)))
    # cloned credentials show up on retail sub-accounts, which back nobody
    leaves = {a["id"] for a in accounts} - {a["parent"] for a in accounts if a["parent"]}
    pool = sorted(a for a in leaves if a not in pin_pts)
    comp = rnd.sample(pool, K["bypasses"])
    for e in events:
        if e["acct"] in comp:
            e["point"] = rnd.choice(hot)
    for a in comp:
        p0 = rnd.choice(hot)
        others = [p for p in hot if p != p0]
        e = {"acct": a, "point": p0, "ts": DAY + rnd.randint(4000, 120000),
             "kwh": rnd.randint(20, 70), "claimed": accmap[a]["class"], "src": 0,
             "inspect": False}
        events.append(e)
        events.append(dict(e, point=rnd.choice(others),
                           ts=e["ts"] + rnd.randint(30, 700), kwh=rnd.randint(20, 70)))
        for _ in range(2):
            events.append({"acct": a, "point": rnd.choice(others),
                           "ts": e["ts"] + rnd.randint(20000, 60000),
                           "kwh": rnd.randint(10, 60), "claimed": accmap[a]["class"],
                           "src": 0, "inspect": False})
    for e in list(events):
        if rnd.random() < 0.18:
            events.append(dict(e, ts=e["ts"] + rnd.randint(1, 5),
                               src=rnd.choice([1, 2]),
                               kwh=e["kwh"] + rnd.randint(0, 3)))
    events.sort(key=lambda e: (e["ts"], e["acct"], e["point"]))
    for _ in range(K["misdeclares"]):
        e = rnd.choice(events)
        cand = [c for c in (1, 2, 3, 4) if c != accmap[e["acct"]]["class"]]
        e["claimed"] = rnd.choice(cand)
    pmap = {p["id"]: p for p in points}
    ucode = {u["id"]: u["code"] for u in utilities}
    by_rep = {}
    for e in events:
        rep = pmap[e["point"]]["utility"]
        if rnd.random() < 0.25:
            rep = rnd.choice(utils)
        by_rep.setdefault(rep, []).append(e)
    segs = []
    sn = 0
    cb, tb = [K["corrupt"]], [K["trunc"]]
    for rep in sorted(by_rep):
        evs = by_rep[rep]
        chunk = max(10, len(evs) // 5)
        for i in range(0, len(evs), chunk):
            block = evs[i:i + chunk]
            if not block:
                continue
            sn += 1
            recs = []
            for k, e in enumerate(block):
                src = e["src"]
                serial = "" if src == 0 else accmap[e["acct"]]["serial"]
                bad = k > 0 and cb[0] > 0 and rnd.random() < 0.05
                if bad:
                    cb[0] -= 1
                recs.append(encode_record(
                    accmap[e["acct"]]["code"] if src == 0 else 0,
                    pmap[e["point"]]["code"], ucode[rep], e["ts"] - DAY, src,
                    e["claimed"], e["inspect"], serial, e["kwh"],
                    rnd.randint(0, 0xFFFF), corrupt=bad))
            cut = 0
            if tb[0] > 0 and len(recs) >= 8 and rnd.random() < 0.4:
                tb[0] -= 1
                lost = rnd.randint(1, 3)
                cut = sum(len(r) for r in recs[-lost:]) - 3
            segs.append(("export-%02d.seg" % sn,
                         encode_segment(len(recs), DAY, rnd.randint(0, 0xFFFF), recs,
                                        truncate_bytes=cut)))
    circ_pairs, expired_ref, superseded_ref = _mk_circulars(
        rnd, roots, accmap, (DAY, t + 10000))
    circs = [parse_circular(txt) for _, txt in circ_pairs]
    reg = Reg(registry)
    ev, fnd, _, _, _ = intake(reg, segs)
    draws = reconstruct(reg, ev)
    detect(reg, draws, fnd)
    pol = Policy(reg, circs)
    live_refs = sorted(c["ref"] for c in pol.live if _in_force(c, draws[0]["ts"]))
    # settlement disputes are filed over the circuits under investigation
    ok_draws = [d for d in draws if d["status"] == "ok" and d["feeder"] in hot_f]
    rnd.shuffle(ok_draws)
    # the weakest hot circuit only reaches its threshold once the upheld disputes have
    # voided their draws: a retroactive void is what locks that circuit out
    own = {}
    for d in draws:
        if d["status"] != "ok":
            own[d["feeder"]] = own.get(d["feeder"], 0) + 1
    weakest = min(hot_f, key=lambda f: own.get(f, 0))
    marg = [d for d in ok_draws if d["feeder"] == weakest][:3]
    ok_draws = marg + [d for d in ok_draws if d not in marg]
    disputes = []
    di = 0
    for d in ok_draws[:7]:
        di += 1
        disputes.append({"id": "DP-%03d" % di, "draw": d["id"],
                         "filed_by": rnd.choice(utils), "basis": rnd.choice(live_refs),
                         "filed_ts": DAY + 500, "ruling": "upheld",
                         "ruled_ts": DAY + 900})
    for d in ok_draws[7:13]:
        di += 1
        disputes.append({"id": "DP-%03d" % di, "draw": d["id"],
                         "filed_by": rnd.choice(utils),
                         "basis": rnd.choice([superseded_ref, expired_ref,
                                              "GRP-26-999"]),
                         "filed_ts": DAY + 500, "ruling": "upheld",
                         "ruled_ts": DAY + 900})
    for d in ok_draws[13:16]:
        di += 1
        disputes.append({"id": "DP-%03d" % di, "draw": d["id"],
                         "filed_by": rnd.choice(utils), "basis": rnd.choice(live_refs),
                         "filed_ts": DAY + 500, "ruling": "rejected",
                         "ruled_ts": DAY + 900})
    disputes.sort(key=lambda x: x["id"])
    # Pick the circuit-condemnation threshold from this corpus's own evidence so that
    # the hot circuits (and only a bounded set) lock out.
    voided, _ = adjudicate(pol, draws, disputes)
    cnt = {f["id"]: 0 for f in feeders}
    for d in draws:
        if d["status"] != "ok" or d["id"] in voided:
            cnt[d["feeder"]] += 1
    hotmin = min(cnt[f] for f in hot_f)
    coldmax = max([cnt[f] for f in cnt if f not in hot_f] or [0])
    if hotmin <= coldmax:
        raise RuntimeError("corpus seed %s: fraud not separable (%d<=%d)"
                           % (seed, hotmin, coldmax))
    registry["condemn_threshold"] = hotmin
    return registry, segs, circ_pairs, disputes


def write_corpus(dirpath, registry, segs, circ_pairs, disputes):
    os.makedirs(os.path.join(dirpath, "exports"), exist_ok=True)
    os.makedirs(os.path.join(dirpath, "circulars"), exist_ok=True)
    with open(os.path.join(dirpath, "registry.json"), "w") as f:
        f.write(json.dumps(registry, indent=1))
    for name, buf in segs:
        with open(os.path.join(dirpath, "exports", name), "wb") as f:
            f.write(buf)
    for ref, text in circ_pairs:
        with open(os.path.join(dirpath, "circulars", ref.lower() + ".txt"), "w") as f:
            f.write(text)
    with open(os.path.join(dirpath, "disputes.jsonl"), "w") as f:
        for d in disputes:
            f.write(jdump(d) + "\n")


def seed_corpus(dirpath, seed, knobs=None):
    raw, segs, circs, disp = make_corpus(seed, knobs)
    write_corpus(dirpath, raw, segs, circs, disp)
    return dirpath
