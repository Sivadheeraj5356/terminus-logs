"""Milestone 5: the evidence review service.

The tribunal reads the closed case over HTTP, so every payload is graded against the
reference settlement itself - the chain-bounded admissions, the supply point's shared
tariff cumulative, the live settlement order and the condemnation cascade all have to be
right before a single response can be.
"""
import json
import os
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

import pytest

import _corpora as C
import _ref

CORPORA = C.corpora(n_hidden=4)


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    p = s.getsockname()[1]
    s.close()
    return p


class Service:
    def __init__(self, data):
        self.db = os.path.join(tempfile.mkdtemp(prefix="db_"), "case.db")
        C.run(["ingest", "--data", data, "--db", self.db])
        self.port = free_port()
        self.proc = subprocess.Popen(
            [C.BIN, "serve", "--db", self.db, "--port", str(self.port)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 45
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", self.port), 0.5):
                    return
            except OSError:
                if self.proc.poll() is not None:
                    raise AssertionError("serve exited early")
                time.sleep(0.15)
        raise AssertionError("serve never came up on port %d" % self.port)

    def get(self, path):
        url = "http://127.0.0.1:%d%s" % (self.port, path)
        try:
            with urllib.request.urlopen(url, timeout=30) as r:
                return r.status, r.read().decode()
        except urllib.error.HTTPError as e:
            return e.code, e.read().decode()

    def stop(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.proc.kill()


@pytest.fixture(scope="module")
def services():
    svc = {name: Service(data) for name, data in CORPORA}
    yield svc
    for s in svc.values():
        s.stop()


def reg_objs(data):
    reg, res = C.expect(data, 3)
    return [{k: r[k] for k in _ref.REG_KEYS} for r in res["register"]]


@pytest.mark.parametrize("name,data", CORPORA, ids=[n for n, _ in CORPORA])
class TestService:
    def test_register_listing(self, name, data, services):
        """GET /register returns 200 with the register objects in register order,
        wrapped as {register, count} with count matching the list length."""
        code, body = services[name].get("/register")
        assert code == 200
        want = reg_objs(data)
        assert body == _ref.jdump({"register": want, "count": len(want)})

    def test_register_detail_and_404(self, name, data, services):
        """GET /register/ID returns the bare register object for a known draw and
        404 with a JSON object body for an unknown id."""
        want = reg_objs(data)
        target = want[len(want) // 2]
        code, body = services[name].get("/register/" + target["id"])
        assert code == 200
        assert body == _ref.jdump(target)
        code, body = services[name].get("/register/NOPE-0:D-NOPE-0:1")
        assert code == 404
        assert isinstance(json.loads(body), dict), "404 body must be a JSON object"

    def test_min_charge_filter(self, name, data, services):
        """GET /register?min_charge keeps only rows whose charged_cents is at least
        the cutoff, preserving order and count."""
        want = reg_objs(data)
        charges = sorted({r["charged_cents"] for r in want if r["charged_cents"] > 0})
        cut = charges[len(charges) // 2] if charges else 1
        code, body = services[name].get("/register?min_charge=%d" % cut)
        assert code == 200
        keep = [r for r in want if r["charged_cents"] >= cut]
        assert body == _ref.jdump({"register": keep, "count": len(keep)})

    def test_status_filter(self, name, data, services):
        """GET /register?status keeps only the rows carrying that status."""
        want = reg_objs(data)
        for st in ("ok", "severed", "replay"):
            code, body = services[name].get("/register?status=" + st)
            assert code == 200
            keep = [r for r in want if r["status"] == st]
            assert body == _ref.jdump({"register": keep, "count": len(keep)})

    def test_combined_filter(self, name, data, services):
        """GET /register with both min_charge and status keeps only the rows that
        pass both filters as a conjunction."""
        want = reg_objs(data)
        code, body = services[name].get("/register?min_charge=1&status=ok")
        assert code == 200
        keep = [r for r in want if r["charged_cents"] >= 1 and r["status"] == "ok"]
        assert body == _ref.jdump({"register": keep, "count": len(keep)})

    def test_findings_listing_and_kind_filter(self, name, data, services):
        """GET /findings returns the findings in emission order, and ?kind keeps
        only the findings of that kind."""
        reg, res = C.expect(data, 3)
        want = _ref.order_findings(res["findings"])
        code, body = services[name].get("/findings")
        assert code == 200
        assert body == _ref.jdump({"findings": want, "count": len(want)})
        for kind in ("tamper", "bypass", "condemnation"):
            code, body = services[name].get("/findings?kind=" + kind)
            assert code == 200
            keep = [f for f in want if f["kind"] == kind]
            assert body == _ref.jdump({"findings": keep, "count": len(keep)})

    def test_earlier_commands_still_work(self, name, data, services):
        """Adding serve does not disturb the earlier settle command, which still
        writes the byte-exact register and summary."""
        reg, res = C.expect(data, 3)
        out = C.run_stage(data, "settle")
        assert C.read(out, "register.jsonl").decode() == _ref.register_text(
            res["register"])
        assert C.read(out, "summary.json").decode() == _ref.jdump(
            _ref.summary_json(reg, res)) + "\n"
