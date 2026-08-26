import hashlib
import json
import os
import pathlib
import random
import subprocess

import pytest


OPS = ("submit", "finish", "hold", "release", "cancel", "pause", "resume", "fault")
VERIFY_PREC = {"BAD_OP": 0, "MISSING_FIELD": 1, "BAD_PAGES": 2}


class Job:
    __slots__ = ("id", "owner", "printer", "priority", "pages", "seq",
                 "state", "faults", "outcomes")

    def __init__(self, jid, owner, printer, priority, pages, seq):
        self.id = jid
        self.owner = owner
        self.printer = printer
        self.priority = priority
        self.pages = pages
        self.seq = seq
        self.state = "queued"
        self.faults = 0
        self.outcomes = []  # list of (seq, outcome)


class Printer:
    __slots__ = ("id", "current", "paused")

    def __init__(self, pid):
        self.id = pid
        self.current = None   # job id or None
        self.paused = False


class Engine:
    def __init__(self, doc, detect):
        self.detect = detect
        self.sid = doc["spool"]
        self.porder = list(doc.get("printers", []))
        self.printers = {p: Printer(p) for p in self.porder}
        self.budgets = dict(doc.get("budgets", {}))
        mf = doc.get("max_faults", 3)
        self.max_faults = mf
        self.jobs = {}          # id -> Job
        self.jorder = []        # job ids in submit order
        self.committed = {}     # owner -> pages finished
        self.reserved = {}      # owner -> pages reserved by printing jobs
        self.committed_pr = {}  # (printer, owner) -> pages finished on that printer
        self.log = []
        self.preemptions = []
        self.aborted = []

    # ---- budget ----
    def remaining(self, owner):
        if owner not in self.budgets:
            return None  # unlimited
        return self.budgets[owner] - self.committed.get(owner, 0) - self.reserved.get(owner, 0)

    def affordable(self, owner, pages):
        rem = self.remaining(owner)
        return rem is None or rem >= pages

    # ---- dispatch ----
    def dispatch(self, pid):
        p = self.printers[pid]
        if p.paused or p.current is not None:
            return
        best = None
        bestkey = None
        for jid in self.jorder:
            j = self.jobs[jid]
            if j.state != "queued" or j.printer != pid:
                continue
            if not self.affordable(j.owner, j.pages):
                continue
            key = (-j.priority, self.committed_pr.get((pid, j.owner), 0), j.seq)
            if best is None or key < bestkey:
                best = jid
                bestkey = key
        if best is None:
            return
        j = self.jobs[best]
        j.state = "printing"
        p.current = best
        self.reserved[j.owner] = self.reserved.get(j.owner, 0) + j.pages

    def try_preempt(self, jid, seq):
        if not self.detect:
            return
        j = self.jobs[jid]
        if j.state != "queued":
            return
        if not self.affordable(j.owner, j.pages):
            return
        p = self.printers[j.printer]
        if p.paused or p.current is None:
            return
        k = self.jobs[p.current]
        if j.priority > k.priority:
            self.reserved[k.owner] = self.reserved.get(k.owner, 0) - k.pages
            k.state = "queued"
            p.current = None
            self.preemptions.append({"at_seq": seq, "printer": p.id,
                                     "victim": k.id, "by": jid})
            self.dispatch(p.id)

    # ---- apply ----
    def apply(self, ev):
        seq = ev["seq"]
        op = ev["op"]
        outcome, jobkey, printerkey = self.dispatch_op(ev, seq)
        self.log.append({"seq": seq, "op": op, "job": jobkey,
                         "printer": printerkey, "outcome": outcome})
        if jobkey is not None and jobkey in self.jobs:
            self.jobs[jobkey].outcomes.append((seq, outcome))

    def dispatch_op(self, ev, seq):
        op = ev["op"]
        if op == "submit":
            return self.op_submit(ev, seq)
        if op == "finish":
            return self.op_finish(ev)
        if op == "hold":
            return self.op_hold(ev)
        if op == "release":
            return self.op_release(ev, seq)
        if op == "cancel":
            return self.op_cancel(ev)
        if op == "pause":
            return self.op_pause(ev)
        if op == "resume":
            return self.op_resume(ev)
        if op == "fault":
            return self.op_fault(ev)
        return "rejected", None, None

    def _is_int(self, v):
        return isinstance(v, int) and not isinstance(v, bool)

    def op_submit(self, ev, seq):
        jid = ev.get("job")
        owner = ev.get("owner")
        printer = ev.get("printer")
        pages = ev.get("pages")
        priority = ev.get("priority")
        bad = (jid is None or owner is None or printer is None
               or not self._is_int(pages) or pages < 1
               or not self._is_int(priority)
               or printer not in self.printers
               or jid in self.jobs)
        if bad:
            return "rejected", jid, printer
        j = Job(jid, owner, printer, priority, pages, seq)
        self.jobs[jid] = j
        self.jorder.append(jid)
        self.dispatch(printer)
        if j.state == "queued":
            self.try_preempt(jid, seq)
        return j.state, jid, printer

    def op_finish(self, ev):
        pid = ev.get("printer")
        if pid not in self.printers:
            return "rejected", None, pid
        p = self.printers[pid]
        if p.current is None:
            return "noop", None, pid
        j = self.jobs[p.current]
        j.state = "done"
        self.committed[j.owner] = self.committed.get(j.owner, 0) + j.pages
        self.committed_pr[(pid, j.owner)] = self.committed_pr.get((pid, j.owner), 0) + j.pages
        self.reserved[j.owner] = self.reserved.get(j.owner, 0) - j.pages
        p.current = None
        self.dispatch(pid)
        return "finished", None, pid

    def op_hold(self, ev):
        jid = ev.get("job")
        if jid is None or jid not in self.jobs:
            return "rejected", jid, None
        j = self.jobs[jid]
        if j.state == "queued":
            j.state = "held"
            return "held", jid, None
        if j.state == "held":
            return "noop", jid, None
        return "rejected", jid, None

    def op_release(self, ev, seq):
        jid = ev.get("job")
        if jid is None or jid not in self.jobs:
            return "rejected", jid, None
        j = self.jobs[jid]
        if j.state == "held":
            j.state = "queued"
            self.dispatch(j.printer)
            if j.state == "queued":
                self.try_preempt(jid, seq)
            return "released", jid, None
        if j.state == "queued":
            return "noop", jid, None
        return "rejected", jid, None

    def op_cancel(self, ev):
        jid = ev.get("job")
        if jid is None or jid not in self.jobs:
            return "rejected", jid, None
        j = self.jobs[jid]
        if j.state in ("done", "canceled", "aborted"):
            return "rejected", jid, None
        if j.state in ("queued", "held"):
            j.state = "canceled"
            return "canceled", jid, None
        # printing
        p = self.printers[j.printer]
        p.current = None
        self.reserved[j.owner] = self.reserved.get(j.owner, 0) - j.pages
        j.state = "canceled"
        self.dispatch(j.printer)
        return "canceled", jid, None

    def op_pause(self, ev):
        pid = ev.get("printer")
        if pid not in self.printers:
            return "rejected", None, pid
        p = self.printers[pid]
        if not p.paused:
            p.paused = True
            return "paused", None, pid
        return "noop", None, pid

    def op_resume(self, ev):
        pid = ev.get("printer")
        if pid not in self.printers:
            return "rejected", None, pid
        p = self.printers[pid]
        if p.paused:
            p.paused = False
            self.dispatch(pid)
            return "resumed", None, pid
        return "noop", None, pid

    def op_fault(self, ev):
        pid = ev.get("printer")
        if pid not in self.printers:
            return "rejected", None, pid
        p = self.printers[pid]
        if p.current is None:
            return "noop", None, pid
        j = self.jobs[p.current]
        j.faults += 1
        self.reserved[j.owner] = self.reserved.get(j.owner, 0) - j.pages
        p.current = None
        if j.faults >= self.max_faults:
            j.state = "aborted"
            self.aborted.append(j.id)
            self.dispatch(pid)
            return "aborted", None, pid
        j.state = "queued"
        self.dispatch(pid)
        return "faulted", None, pid


# ---- structural verify (no replay) ----
def verify(doc):
    best = None  # (seq, reason)
    for ev in doc["events"]:
        seq = ev.get("seq")
        op = ev.get("op")
        reasons = []
        if op not in OPS:
            reasons.append("BAD_OP")
        elif op == "submit":
            if (ev.get("job") is None or ev.get("owner") is None
                    or ev.get("printer") is None or ev.get("pages") is None
                    or ev.get("priority") is None):
                reasons.append("MISSING_FIELD")
            pg = ev.get("pages")
            if pg is not None and (not isinstance(pg, int) or isinstance(pg, bool) or pg < 1):
                reasons.append("BAD_PAGES")
        elif op in ("finish", "pause", "resume", "fault"):
            if ev.get("printer") is None:
                reasons.append("MISSING_FIELD")
        elif op in ("hold", "release", "cancel"):
            if ev.get("job") is None:
                reasons.append("MISSING_FIELD")
        if reasons:
            r = min(reasons, key=lambda x: VERIFY_PREC[x])
            if best is None or seq < best[0]:
                best = (seq, r)
    return best


def build(doc, detect):
    e = Engine(doc, detect)
    for ev in doc["events"]:
        e.apply(ev)
    return e


# ---- output builders ----
def out_log(e):
    return {"spool": e.sid, "events": list(e.log)}


def out_printers(e):
    rows = []
    for pid in sorted(e.printers):
        p = e.printers[pid]
        rows.append({"printer": pid, "current": p.current, "paused": p.paused})
    return {"spool": e.sid, "printers": rows}


def out_queues(e):
    rows = []
    for pid in sorted(e.printers):
        q = []
        for jid in e.jorder:
            j = e.jobs[jid]
            if j.printer == pid and j.state in ("queued", "held"):
                q.append({"job": j.id, "owner": j.owner, "priority": j.priority,
                          "pages": j.pages, "state": j.state})
        if q:
            rows.append({"printer": pid, "queue": q})
    return {"spool": e.sid, "printers": rows}


def out_jobs(e):
    rows = []
    for jid in sorted(e.jobs):
        j = e.jobs[jid]
        rows.append({"job": j.id, "owner": j.owner, "printer": j.printer,
                     "priority": j.priority, "pages": j.pages, "state": j.state})
    return {"spool": e.sid, "jobs": rows}


def out_owners(e):
    names = set(e.budgets) | {e.jobs[j].owner for j in e.jobs}
    rows = []
    for o in sorted(names):
        b = e.budgets.get(o)
        c = e.committed.get(o, 0)
        r = e.reserved.get(o, 0)
        rem = None if b is None else b - c - r
        rows.append({"owner": o, "budget": b, "committed": c,
                     "reserved": r, "remaining": rem})
    return {"spool": e.sid, "owners": rows}


def out_verify(doc):
    err = verify(doc)
    return {"spool": doc["spool"], "ok": err is None,
            "error": None if err is None else {"seq": err[0], "reason": err[1]}}


def out_preemptions(e):
    return {"spool": e.sid, "events": list(e.preemptions), "count": len(e.preemptions)}


def out_aborts(e):
    return {"spool": e.sid, "aborted": list(e.aborted), "count": len(e.aborted)}


def out_job(e, jid):
    j = e.jobs.get(jid)
    if j is None:
        return {"spool": e.sid, "job": jid, "state": "unknown", "printer": None,
                "owner": None, "priority": None, "pages": None, "faults": 0,
                "outcomes": []}
    return {"spool": e.sid, "job": j.id, "state": j.state, "printer": j.printer,
            "owner": j.owner, "priority": j.priority, "pages": j.pages,
            "faults": j.faults,
            "outcomes": [{"seq": s, "outcome": o} for (s, o) in j.outcomes]}


def canon(obj):
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def run(doc, args, detect):
    cmd = args[0]
    if cmd == "verify":
        return canon(out_verify(doc))
    if cmd == "trace":
        n = int(args[1])
        if n < 0:
            n = 0
        elif n > len(doc["events"]):
            n = len(doc["events"])
        sub_doc = {"spool": doc["spool"], "printers": doc.get("printers", []),
                   "budgets": doc.get("budgets", {}),
                   "max_faults": doc.get("max_faults", 3),
                   "events": doc["events"][:n]}
        e = build(sub_doc, detect)
        return canon(out_printers(e))
    e = build(doc, detect)
    if cmd == "log":
        return canon(out_log(e))
    if cmd == "printers":
        return canon(out_printers(e))
    if cmd == "queues":
        return canon(out_queues(e))
    if cmd == "jobs":
        return canon(out_jobs(e))
    if cmd == "owners":
        return canon(out_owners(e))
    if cmd == "preemptions":
        return canon(out_preemptions(e))
    if cmd == "aborts":
        return canon(out_aborts(e))
    if cmd == "job":
        return canon(out_job(e, args[1]))
    raise SystemExit("unknown command: %s" % cmd)


def gen_schedule(rng, m2, sid, nev):
    npr = 2 if rng.random() < 0.6 else 3
    printers = ["p%d" % (i + 1) for i in range(npr)]
    owners = ["A", "B", "C"]
    budgets = {}
    for o in owners:
        if rng.random() < 0.55:
            budgets[o] = rng.randint(4, 12)
    events = []
    jobids = []
    jc = 0
    job_ops = ("hold", "release", "cancel")
    printer_ops = ("finish", "pause", "resume", "fault") if m2 else ("finish", "pause", "resume")
    for i in range(nev):
        seq = i + 1
        roll = rng.random()
        if roll < 0.5 or not jobids:
            jc += 1
            jid = "j%d" % jc
            jobids.append(jid)
            ev = {"seq": seq, "op": "submit", "job": jid,
                  "owner": rng.choice(owners), "printer": rng.choice(printers),
                  "pages": rng.randint(1, 4), "priority": rng.randint(1, 3)}
        elif roll < 0.78:
            ev = {"seq": seq, "op": rng.choice(printer_ops),
                  "printer": rng.choice(printers)}
        else:
            ev = {"seq": seq, "op": rng.choice(job_ops), "job": rng.choice(jobids)}
        events.append(ev)
    doc = {"spool": sid, "printers": printers, "budgets": budgets, "events": events}
    if m2:
        doc["max_faults"] = rng.randint(2, 3)
    return doc


# ==== behavior-based verifier harness ====
# The candidate `spoold` binary implements the FULL model (preemption + faults),
# so the reference is always run with detection enabled. Every command output is
# compared byte-for-byte against this independent Python reference on hidden
# schedules; no reference outputs are stored on disk.
APP = "/app"
BIN = "/app/bin/spoold"
DETECT = True
GT = pathlib.Path(__file__).parent / "gt"
CMDS = ["log", "printers", "queues", "jobs", "owners", "verify",
        "preemptions", "aborts"]


_BUILT = False


def _build():
    # Always (re)compile the binary from /app/internal/sp/sp.go exactly once per
    # test session, ignoring any executable that already sits at BIN. This makes
    # the build check carry real signal: the graded binary is guaranteed to be
    # the product of the current Go source (a stale or non-Go executable left at
    # BIN cannot pass).
    global _BUILT
    if not _BUILT:
        subprocess.run(["go", "build", "-o", BIN, "./cmd/spoold"], cwd=APP, check=True)
        _BUILT = True


def run_bin(cli):
    _build()
    r = subprocess.run([BIN] + cli, cwd=APP, capture_output=True, text=True)
    return r.returncode, r.stdout, r.stderr


def load(path):
    with open(path) as f:
        return json.load(f)


def expect(cli):
    doc = load(cli[1])
    return run(doc, [cli[0]] + cli[2:], DETECT)


def check(cli):
    rc, out, err = run_bin(cli)
    assert rc == 0, "cmd %s failed: %s" % (cli, err)
    assert out == expect(cli), "mismatch for %s" % cli


def jload(cli):
    return json.loads(run_bin(cli)[1])


def _hash_dir(d):
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(pathlib.Path(d).glob("*.json"))}


def fixtures():
    return sorted(str(p) for p in GT.glob("*.json"))


def _jobids(f):
    seen = []
    for ev in load(f)["events"]:
        j = ev.get("job")
        if ev.get("op") == "submit" and j is not None and j not in seen:
            seen.append(j)
    return seen


class TestSpoold:
    def test_build(self):
        _build()
        assert os.path.exists(BIN)

    def test_canonical_format(self):
        """Output is sort-keys, 2-space-indented JSON with a trailing newline."""
        f = str(GT / "skip_unaffordable.json")
        rc, out, err = run_bin(["printers", f])
        assert rc == 0, err
        obj = json.loads(out)
        assert out == json.dumps(obj, indent=2, sort_keys=True) + "\n"
        assert out.endswith("}\n")

    @pytest.mark.parametrize("f", fixtures())
    def test_all_commands_match_reference(self, f):
        """Every command on every hidden schedule matches the reference."""
        for c in CMDS:
            check([c, f])
        for t in _jobids(f) + ["ZZZ"]:
            check(["job", f, t])
        ne = len(load(f)["events"])
        for n in (0, 1, ne // 2, ne, ne + 5, -2):
            check(["trace", f, str(n)])

    # ---- pinned divergence literals: dispatch / quota / fair-share (§3–§6) ----
    def test_skip_unaffordable(self):
        """A lower-priority affordable job dispatches ahead of an unaffordable one."""
        f = str(GT / "skip_unaffordable.json")
        assert jload(["printers", f])["printers"] == [
            {"current": "small", "paused": False, "printer": "p1"}]
        assert jload(["queues", f])["printers"] == [
            {"printer": "p1", "queue": [
                {"job": "big", "owner": "poor", "pages": 10,
                 "priority": 9, "state": "queued"}]}]
        assert [(e["seq"], e["outcome"]) for e in jload(["log", f])["events"]] == [
            (1, "queued"), (2, "printing")]

    def test_budget_exact(self):
        """A job costing exactly the remaining budget is affordable."""
        f = str(GT / "budget_exact.json")
        assert [(e["seq"], e["outcome"]) for e in jload(["log", f])["events"]] == [
            (1, "printing"), (2, "queued")]
        assert jload(["owners", f])["owners"] == [
            {"budget": 5, "committed": 0, "owner": "A", "remaining": 0, "reserved": 5}]

    def test_local_dispatch(self):
        """Freeing quota on one printer does not dispatch a different printer."""
        f = str(GT / "local_dispatch.json")
        jobs = {j["job"]: j["state"] for j in jload(["jobs", f])["jobs"]}
        assert jobs == {"j1": "canceled", "j2": "queued"}
        assert jload(["printers", f])["printers"] == [
            {"current": None, "paused": False, "printer": "p1"},
            {"current": None, "paused": False, "printer": "p2"}]

    def test_fair_share_tiebreak(self):
        """Equal-priority tie goes to the owner with fewer pages committed here."""
        f = str(GT / "fair_share.json")
        assert jload(["printers", f])["printers"][0]["current"] == "b1"

    def test_release_retains_seq(self):
        """A released job keeps its submit position and can leapfrog a later job."""
        f = str(GT / "release_retains_seq.json")
        assert jload(["printers", f])["printers"][0]["current"] == "j2"

    def test_noop_and_reject(self):
        """Re-hold of a held job is noop; ops on a terminal job are rejected."""
        f = str(GT / "noop_reject.json")
        assert [(e["seq"], e["outcome"]) for e in jload(["log", f])["events"]] == [
            (1, "printing"), (2, "queued"), (3, "held"), (4, "noop"),
            (5, "released"), (6, "canceled"), (7, "rejected")]

    def test_cancel_printing_redispatch(self):
        """Canceling a printing job frees the printer and re-dispatches it."""
        f = str(GT / "cancel_printing_redispatch.json")
        assert jload(["printers", f])["printers"][0]["current"] == "j2"

    def test_pause_finish(self):
        """A paused printer finishes its current job but dispatches nothing new."""
        f = str(GT / "pause_finish.json")
        assert [(e["seq"], e["outcome"]) for e in jload(["log", f])["events"]] == [
            (1, "printing"), (2, "queued"), (3, "paused"),
            (4, "finished"), (5, "resumed")]
        assert jload(["printers", f])["printers"][0] == {
            "current": "j2", "paused": False, "printer": "p1"}

    def test_reject_unknown(self):
        """Undeclared printer and duplicate job id both reject."""
        f = str(GT / "reject_unknown.json")
        assert [(e["seq"], e["outcome"]) for e in jload(["log", f])["events"]] == [
            (1, "rejected"), (2, "printing"), (3, "rejected"), (4, "rejected")]

    def test_verify(self):
        """Structural verify: precedence and earliest seq."""
        assert jload(["verify", str(GT / "verify_bad.json")])["error"] == \
            {"reason": "BAD_PAGES", "seq": 2}
        assert jload(["verify", str(GT / "verify_missing.json")])["error"] == \
            {"reason": "MISSING_FIELD", "seq": 2}
        assert jload(["verify", str(GT / "verify_clean.json")]) == \
            {"spool": "verify_clean", "ok": True, "error": None}

    def test_trace_clamps(self):
        """trace clamps n to [0, len(events)]."""
        f = str(GT / "pause_finish.json")
        ne = len(load(f)["events"])
        assert jload(["trace", f, "-3"])["printers"] == jload(["trace", f, "0"])["printers"]
        assert run_bin(["trace", f, str(ne + 9)])[1] == run_bin(["printers", f])[1]
        check(["trace", f, "0"])
        check(["trace", f, str(ne)])

    # ---- pinned divergence literals: preemption / faults (§7–§8) ----
    def test_preempt_basic(self):
        """A strictly-higher-priority arrival preempts a lower printing job."""
        f = str(GT / "preempt_basic.json")
        assert jload(["preemptions", f])["events"] == [
            {"at_seq": 2, "by": "hi", "printer": "p1", "victim": "lo"}]
        assert jload(["printers", f])["printers"][0]["current"] == "hi"

    def test_preempt_equal_no(self):
        """Equal priority does not preempt."""
        f = str(GT / "preempt_equal_no.json")
        assert jload(["preemptions", f])["count"] == 0
        assert jload(["printers", f])["printers"][0]["current"] == "lo"

    def test_preempt_selfblock(self):
        """A same-owner reservation held by the victim can block preemption."""
        f = str(GT / "preempt_selfblock.json")
        assert jload(["preemptions", f])["count"] == 0
        assert jload(["printers", f])["printers"][0]["current"] == "lo"

    def test_preempt_third_wins(self):
        """Preemption frees the printer, then a higher queued job is dispatched."""
        f = str(GT / "preempt_third_wins.json")
        assert jload(["preemptions", f])["events"] == [
            {"at_seq": 5, "by": "mid", "printer": "p1", "victim": "lo"}]
        assert jload(["printers", f])["printers"][0]["current"] == "top"

    def test_release_preempts(self):
        """A released job can preempt the lower job that ran while it was held."""
        f = str(GT / "release_preempts.json")
        assert jload(["preemptions", f])["events"] == [
            {"at_seq": 6, "by": "hi", "printer": "p1", "victim": "lo"}]
        assert jload(["printers", f])["printers"][0]["current"] == "hi"

    def test_crashloop_abort(self):
        """A job faulted up to max_faults is aborted."""
        f = str(GT / "crashloop_abort.json")
        assert jload(["aborts", f]) == {
            "spool": "crashloop_abort", "aborted": ["j"], "count": 1}
        j = jload(["job", f, "j"])
        assert j["state"] == "aborted"
        assert j["faults"] == 2

    def test_fault_retry_then_next(self):
        """After a fault re-queues a job, a higher-priority waiter is dispatched."""
        f = str(GT / "fault_retry_then_next.json")
        assert jload(["printers", f])["printers"][0]["current"] == "k"

    def test_no_preempt_reports_empty(self):
        """A schedule with no preemption or abort reports zero of each."""
        f = str(GT / "no_preempt.json")
        assert jload(["preemptions", f])["count"] == 0
        assert jload(["aborts", f])["count"] == 0

    def test_unknown_job(self):
        """An unknown job id reports the unknown shape."""
        f = str(GT / "preempt_basic.json")
        assert jload(["job", f, "nope"]) == {
            "spool": "preempt_basic", "job": "nope", "state": "unknown",
            "printer": None, "owner": None, "priority": None, "pages": None,
            "faults": 0, "outcomes": []}

    def test_inputs_not_mutated(self):
        """The binary must never write to its input fixtures."""
        before = _hash_dir(GT)
        for f in fixtures():
            for c in CMDS:
                run_bin([c, f])
        assert _hash_dir(GT) == before

    def test_random_preemption_free_schedules(self):
        """150 seeded random preemption-free schedules match the reference.

        Any draw in which the full-specification preemption rule (§7) would fire
        is discarded, so the graded output is identical whether or not an
        implementation applies preemption; this exercises the §3–§6/§9 core in
        isolation.
        """
        rng = random.Random(4242001)
        work = pathlib.Path("/tmp/sp_pf")
        work.mkdir(parents=True, exist_ok=True)
        made = 0
        while made < 150:
            doc = gen_schedule(rng, False, "R%d" % made, rng.randint(1, 30))
            if build(doc, True).preemptions:
                continue
            p = work / ("r%04d.json" % made)
            json.dump(doc, open(p, "w"))
            for c in CMDS:
                check([c, str(p)])
            check(["trace", str(p), str(rng.randint(0, len(doc["events"])))])
            made += 1

    def test_random_full_schedules(self):
        """150 seeded random schedules (with faults/preemption) match the reference."""
        rng = random.Random(9090002)
        work = pathlib.Path("/tmp/sp_full")
        work.mkdir(parents=True, exist_ok=True)
        for i in range(150):
            doc = gen_schedule(rng, True, "R%d" % i, rng.randint(4, 36))
            p = work / ("r%04d.json" % i)
            json.dump(doc, open(p, "w"))
            for c in CMDS:
                check([c, str(p)])
            for t in _jobids(str(p)):
                check(["job", str(p), t])
