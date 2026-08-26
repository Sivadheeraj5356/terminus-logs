import json
import os
import subprocess
import uuid

import pytest

REPORT = "/app/report.json"
BASE_TOTAL_REQUESTS = 15
BASE_INVALID_COUNT = 4
BASE_ERROR_REQUESTS = 4
BASE_TOTAL_BYTES = 10048


@pytest.fixture(scope="module")
def report() -> dict:
    assert os.path.isfile(REPORT), f"{REPORT} does not exist"
    with open(REPORT, encoding="utf-8") as fh:
        data = json.load(fh)
    assert isinstance(data, dict), "report.json must be a JSON object"
    return data


def rerun_report() -> dict:
    result = subprocess.run(
        ["node", "/app/dist/index.js"],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    with open(REPORT, encoding="utf-8") as fh:
        return json.load(fh)


def test_report_top_level_keys(report):
    """Report exposes the required contract and no extra top-level fields."""
    required = {
        "total_requests", "invalid_count", "error_requests",
        "total_bytes_transferred", "status_breakdown", "methods_breakdown",
        "top_ips_by_bytes", "top_urls_by_requests", "hourly_requests",
    }
    assert set(report.keys()) == required


def test_total_requests(report):
    """Base logs count only valid nonblank CLF entries as requests."""
    assert report["total_requests"] == BASE_TOTAL_REQUESTS


def test_invalid_count(report):
    """Base logs count malformed nonblank entries without counting blank lines."""
    assert report["invalid_count"] == BASE_INVALID_COUNT


def test_error_requests(report):
    """Base logs count valid 4xx and 5xx responses as errors."""
    assert report["error_requests"] == BASE_ERROR_REQUESTS


def test_total_bytes_transferred(report):
    """Base logs sum bytes from valid entries, including zero-byte forms."""
    assert report["total_bytes_transferred"] == BASE_TOTAL_BYTES


def test_status_breakdown_structure(report):
    """Status breakdown contains exactly the five status-class buckets."""
    sb = report["status_breakdown"]
    assert isinstance(sb, dict)
    assert set(sb.keys()) == {"1xx", "2xx", "3xx", "4xx", "5xx"}


def test_status_breakdown_values(report):
    """Status class totals match the valid base log entries."""
    assert report["status_breakdown"] == {
        "1xx": 0,
        "2xx": 9,
        "3xx": 2,
        "4xx": 3,
        "5xx": 1,
    }


def test_methods_breakdown(report):
    """Method counts preserve request methods from valid entries."""
    mb = report["methods_breakdown"]
    assert isinstance(mb, dict)
    assert mb.get("GET") == 11
    assert mb.get("POST") == 2
    assert mb.get("DELETE") == 1
    assert mb.get("PUT") == 1


def test_top_ips_by_bytes_count(report):
    """The IP ranking includes five entries when at least five IPs exist."""
    top = report["top_ips_by_bytes"]
    assert isinstance(top, list)
    assert len(top) == 5


def test_top_ips_by_bytes_structure(report):
    """Each ranked IP entry has the documented shape and primitive types."""
    for entry in report["top_ips_by_bytes"]:
        assert set(entry.keys()) == {"ip", "bytes"}
        assert isinstance(entry["ip"], str)
        assert isinstance(entry["bytes"], int)


def test_top_ips_by_bytes_first(report):
    """The highest-byte source IP appears first with its byte total."""
    top = report["top_ips_by_bytes"]
    assert top[0]["ip"] == "192.168.1.20"
    assert top[0]["bytes"] == 4352


def test_top_ips_by_bytes_not_by_requests(report):
    """IP ranking is based on transferred bytes, not request frequency."""
    top = report["top_ips_by_bytes"]
    assert top[0]["ip"] != "192.168.1.10"
    positions = [e["ip"] for e in top]
    assert "192.168.1.10" in positions
    assert positions.index("192.168.1.10") == 2


def test_top_ips_by_bytes_order(report):
    """IP ranking orders by bytes descending with lexicographic ties."""
    assert report["top_ips_by_bytes"] == [
        {"ip": "192.168.1.20", "bytes": 4352},
        {"ip": "10.0.0.1", "bytes": 2176},
        {"ip": "192.168.1.10", "bytes": 1536},
        {"ip": "10.0.0.3", "bytes": 1024},
        {"ip": "192.168.1.70", "bytes": 512},
    ]


def test_top_urls_count(report):
    """The URL ranking includes five entries when at least five URLs exist."""
    top = report["top_urls_by_requests"]
    assert isinstance(top, list)
    assert len(top) == 5


def test_top_urls_structure(report):
    """Each ranked URL entry has the documented shape and primitive types."""
    for entry in report["top_urls_by_requests"]:
        assert set(entry.keys()) == {"url", "requests"}
        assert isinstance(entry["url"], str)
        assert isinstance(entry["requests"], int)


def test_top_urls_first(report):
    """The most requested normalized URL appears first."""
    top = report["top_urls_by_requests"]
    assert top[0]["url"] == "/index.html"
    assert top[0]["requests"] == 3


def test_top_urls_query_string_stripped(report):
    """URL aggregation removes query strings before counting."""
    top = report["top_urls_by_requests"]
    api_data = next((e for e in top if e["url"] == "/api/data"), None)
    assert api_data is not None
    assert api_data["requests"] == 2
    assert all("?" not in e["url"] for e in top)


def test_top_urls_tie_breaking(report):
    """URL ties are ordered lexicographically after request counts."""
    top = report["top_urls_by_requests"]
    assert [entry["url"] for entry in top[1:4]] == [
        "/admin",
        "/api/data",
        "/api/health",
    ]


def test_hourly_requests_structure(report):
    """Hourly counts use two-digit string UTC hours with positive counts."""
    hr = report["hourly_requests"]
    assert isinstance(hr, dict)
    for k, v in hr.items():
        assert isinstance(k, str) and len(k) == 2 and k.isdigit()
        assert isinstance(v, int) and v > 0


def test_hourly_requests_utc_conversion(report):
    """Base timestamps are converted to UTC hours before aggregation."""
    hr = report["hourly_requests"]
    assert hr.get("08") == 10
    assert hr.get("02") == 5
    assert "09" not in hr


def test_dash_bytes_treated_as_zero(report):
    """A dash byte field is valid and contributes zero bytes."""
    assert report["invalid_count"] == BASE_INVALID_COUNT
    assert report["total_requests"] == BASE_TOTAL_REQUESTS


def test_status_boundary_99_rejected(report):
    """Status values below the valid HTTP range are rejected."""
    assert report["total_requests"] == BASE_TOTAL_REQUESTS


def test_single_token_request_rejected(report):
    """A quoted request that does not split into three tokens is rejected."""
    assert report["invalid_count"] == BASE_INVALID_COUNT


class TestDynamicInput:
    EXTRA = "/app/logs/zz_audit_extra.log"

    EXTRA_VALID = [
        '10.9.8.7 - - [20/Jun/2024:10:00:00 +0500] "GET /probe HTTP/1.1" 200 77 "-" "Probe/2.0"',
        '10.9.8.7 - - [20/Jun/2024:10:00:01 +0500] "GET /probe HTTP/1.1" 503 0 "-" "Probe/2.0"',
    ]
    EXTRA_INVALID = [
        "this is not a clf line",
    ]
    EXTRA_UTC_HOUR = "05"

    def setup_method(self):
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.EXTRA_VALID + self.EXTRA_INVALID:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.EXTRA):
            os.unlink(self.EXTRA)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_totals_increase_with_extra_file(self):
        """A new regular log file is included when the report is rerun."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.EXTRA_VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.EXTRA_INVALID)
        assert r["status_breakdown"]["5xx"] >= 2
        assert r["hourly_requests"].get(self.EXTRA_UTC_HOUR) == len(self.EXTRA_VALID)


class TestAdversarialInput:
    EXTRA = "/app/logs/00_edge_extra.log"

    VALID = [
        '198.51.100.20 - - [12/Jul/2024:00:15:00 +0530] "PATCH /tie?b=1 HTTP/2.0" 100 6000 "-" "Edge/1.0"',
        '198.51.100.3 - - [12/Jul/2024:23:45:00 -0330] "PATCH /tie?b=2 HTTP/2.0" 599 6000 "-" "Edge/1.0"',
        '198.51.100.11 - - [12/Jul/2024:00:10:00 +0545] "GET /floor HTTP/1.1" 200 6000 "-" "Edge/1.0"',
        '203.0.113.9 - - [12/Jul/2024:04:00:00 +0000] "GET /zero HTTP/1.1" 204 - "-" "Edge/1.0"',
    ]
    INVALID = [
        '203.0.113.10 - - [12/Jul/2024:04:00:01 +0000] "GET /bad HTTP/1.1" 600 1 "-" "Edge/1.0"',
        '203.0.113.11 - - [12/Jul/2024:04:00:02 +0000] "GET /bad HTTP/1.1" 200 -1 "-" "Edge/1.0"',
        '203.0.113.12 - - [12/Jul/2024:04:00:03 +0000] "GET /too many HTTP/1.1 EXTRA" 200 1 "-" "Edge/1.0"',
        "   ",
    ]

    def setup_method(self):
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.VALID + self.INVALID:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.EXTRA):
            os.unlink(self.EXTRA)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_edge_cases_are_accounted_for(self):
        """Mixed boundary statuses, bytes, offsets, and blank lines are handled."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + 3
        assert r["error_requests"] == BASE_ERROR_REQUESTS + 1
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 18000

        assert r["status_breakdown"]["1xx"] == 1
        assert r["status_breakdown"]["2xx"] == 11
        assert r["status_breakdown"]["5xx"] == 2
        assert r["methods_breakdown"]["PATCH"] == 2

        assert r["hourly_requests"].get("18") == 2
        assert r["hourly_requests"].get("03") == 1
        assert r["hourly_requests"].get("04") == 1
        assert "00" not in r["hourly_requests"]
        assert "23" not in r["hourly_requests"]

        assert r["top_ips_by_bytes"][:3] == [
            {"ip": "198.51.100.11", "bytes": 6000},
            {"ip": "198.51.100.20", "bytes": 6000},
            {"ip": "198.51.100.3", "bytes": 6000},
        ]
        tie_url = next((e for e in r["top_urls_by_requests"] if e["url"] == "/tie"), None)
        assert tie_url == {"url": "/tie", "requests": 2}
        assert all("?" not in e["url"] for e in r["top_urls_by_requests"])


class TestStrictParsingInput:
    EXTRA = "/app/logs/mm_strict_extra.log"
    SHADOW = "/app/logs/ll_shadow.txt"

    VALID = [
        '2001:db8::1 - jane [29/Feb/2024:00:05:00 +1245] "HEAD /leap?x=1 HTTP/1.0" 299 42 "-" "Strict/1.0"',
        '198.51.100.2 ident user [01/Mar/2024:00:00:00 -0001] "OPTIONS /minute HTTP/1.1" 399 8 "-" "Strict/1.0"',
    ]
    INVALID = [
        ' 203.0.113.20 - - [01/Mar/2024:00:00:00 +0000] "GET /leading HTTP/1.1" 200 1 "-" "Strict/1.0"',
        '203.0.113.21 - - [01/Mar/2024:00:00:00 +0000] "GET /trailing HTTP/1.1" 200 1 "-" "Strict/1.0" ',
        '203.0.113.22 - - [31/Apr/2024:00:00:00 +0000] "GET /date HTTP/1.1" 200 1 "-" "Strict/1.0"',
        '203.0.113.23 - - [01/Foo/2024:00:00:00 +0000] "GET /month HTTP/1.1" 200 1 "-" "Strict/1.0"',
        '203.0.113.24 - - [01/Mar/2024:24:00:00 +0000] "GET /hour HTTP/1.1" 200 1 "-" "Strict/1.0"',
        '203.0.113.25 - - [01/Mar/2024:00:60:00 +0000] "GET /minute HTTP/1.1" 200 1 "-" "Strict/1.0"',
        '203.0.113.26 - - [01/Mar/2024:00:00:00 +2460] "GET /zone HTTP/1.1" 200 1 "-" "Strict/1.0"',
    ]
    SHADOW_LINES = [
        '198.51.100.200 - - [01/Mar/2024:00:00:00 +0000] "GET /shadow HTTP/1.1" 200 999999 "-" "Strict/1.0"',
    ]

    def setup_method(self):
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.VALID + self.INVALID:
                fh.write(line + "\n")
        with open(self.SHADOW, "w", encoding="utf-8") as fh:
            for line in self.SHADOW_LINES:
                fh.write(line + "\n")

    def teardown_method(self):
        for filename in (self.EXTRA, self.SHADOW):
            if os.path.exists(filename):
                os.unlink(filename)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_strict_parsing_and_log_selection(self):
        """Strict validation rejects malformed dates and ignores non-log files."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.INVALID)
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 50

        assert r["methods_breakdown"]["HEAD"] == 1
        assert r["methods_breakdown"]["OPTIONS"] == 1
        assert r["status_breakdown"]["2xx"] == 10
        assert r["status_breakdown"]["3xx"] == 3

        assert r["hourly_requests"].get("11") == 1
        assert r["hourly_requests"].get("00") == 1
        assert all(entry["url"] != "/shadow" for entry in r["top_urls_by_requests"])
        assert all(entry["ip"] != "198.51.100.200" for entry in r["top_ips_by_bytes"])


class TestFilesystemAndRequestTokenEdges:
    EXTRA = "/app/logs/ab_token_edges.log"
    TRAP_DIR = "/app/logs/aa_directory_trap.log"

    VALID = [
        '198.51.100.50 - - [29/Feb/2000:23:30:00 -0030] "GET /century-ok?drop=this HTTP/1.1" 200 321 "-" "Hard/1.0"',
        '198.51.100.51 - - [01/Jan/2024:00:15:00 +1400] "POST /roll-back HTTP/1.1" 201 654 "-" "Hard/1.0"',
        '198.51.100.56 - - [01/Jan/2024:23:59:59 +2300] "GET /offset-edge HTTP/1.1" 204 111 "-" "Hard/1.0"',
    ]
    INVALID = [
        '198.51.100.52 - - [29/Feb/1900:00:00:00 +0000] "GET /century-bad HTTP/1.1" 200 1 "-" "Hard/1.0"',
        '198.51.100.53 - - [01/Jan/2024:00:00:00 +0000] "GET /missing-protocol " 200 1 "-" "Hard/1.0"',
        '198.51.100.54 - - [01/Jan/2024:00:00:00 +0000] " /missing-method HTTP/1.1" 200 1 "-" "Hard/1.0"',
        '198.51.100.55 - - [01/Jan/2024:00:00:00 +0000] "GET  HTTP/1.1" 200 1 "-" "Hard/1.0"',
        '198.51.100.57 - - [01/Jan/2024:00:00:60 +0000] "GET /bad-second HTTP/1.1" 200 1 "-" "Hard/1.0"',
        '198.51.100.58 - - [01/Jan/2024:00:00:00 +2400] "GET /bad-offset HTTP/1.1" 200 1 "-" "Hard/1.0"',
    ]

    def setup_method(self):
        os.makedirs(self.TRAP_DIR, exist_ok=True)
        with open(os.path.join(self.TRAP_DIR, "ignored"), "w", encoding="utf-8") as fh:
            fh.write(
                '203.0.113.250 - - [01/Jan/2024:00:00:00 +0000] '
                '"GET /directory-trap HTTP/1.1" 200 999999 "-" "Hard/1.0"\n'
            )
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.VALID + self.INVALID:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.EXTRA):
            os.unlink(self.EXTRA)
        trap_file = os.path.join(self.TRAP_DIR, "ignored")
        if os.path.exists(trap_file):
            os.unlink(trap_file)
        if os.path.isdir(self.TRAP_DIR):
            os.rmdir(self.TRAP_DIR)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_directories_and_empty_request_tokens(self):
        """Directory entries and empty request tokens do not enter statistics."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.INVALID)
        assert r["error_requests"] == BASE_ERROR_REQUESTS
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 1086

        assert r["status_breakdown"]["2xx"] == 12
        assert r["methods_breakdown"]["GET"] == 13
        assert r["methods_breakdown"]["POST"] == 3

        assert r["hourly_requests"].get("00") == 2
        assert r["hourly_requests"].get("10") == 1
        assert all(entry["url"] != "/directory-trap" for entry in r["top_urls_by_requests"])


class TestSmallCorpusTopIps:
    def setup_method(self):
        self.token = uuid.uuid4().hex[:8]
        self.hold = f"/app/logs/.hold_{self.token}"
        self.extra = "/app/logs/zz_small_corpus.log"
        os.makedirs(self.hold, exist_ok=True)
        self.moved = []
        for name in os.listdir("/app/logs"):
            src = os.path.join("/app/logs", name)
            if os.path.isfile(src) and name.endswith(".log"):
                dst = os.path.join(self.hold, name)
                os.rename(src, dst)
                self.moved.append((src, dst))

        lines = [
            '10.1.0.1 - - [01/May/2024:00:00:00 +0000] "GET /a HTTP/1.1" 200 5 "-" "Small/1.0"',
            '10.1.0.2 - - [01/May/2024:01:00:00 +0000] "GET /b HTTP/1.1" 200 30 "-" "Small/1.0"',
            '10.1.0.1 - - [01/May/2024:02:00:00 +0000] "POST /a HTTP/1.1" 404 7 "-" "Small/1.0"',
            '10.1.0.3 - - [01/May/2024:03:00:00 +0000] "GET /c HTTP/1.1" 204 1 "-" "Small/1.0"',
        ]
        with open(self.extra, "w", encoding="utf-8") as fh:
            for line in lines:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.extra):
            os.unlink(self.extra)
        for src, dst in reversed(self.moved):
            if os.path.exists(dst):
                os.rename(dst, src)
        if os.path.isdir(self.hold):
            os.rmdir(self.hold)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_top_ips_includes_all_when_fewer_than_five(self):
        """Top lists shrink naturally when fewer than five distinct values exist."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == 4
        assert r["invalid_count"] == 0
        assert r["error_requests"] == 1
        assert r["total_bytes_transferred"] == 43
        assert r["top_ips_by_bytes"] == [
            {"ip": "10.1.0.2", "bytes": 30},
            {"ip": "10.1.0.1", "bytes": 12},
            {"ip": "10.1.0.3", "bytes": 1},
        ]
        assert r["top_urls_by_requests"] == [
            {"url": "/a", "requests": 2},
            {"url": "/b", "requests": 1},
            {"url": "/c", "requests": 1},
        ]


class TestQuotedFieldAndNumericEdges:
    EXTRA = "/app/logs/yy_quoted_fields.log"

    VALID = [
        '203.0.113.100 cache alice [31/Dec/2024:23:30:00 -0030] "GET /ua?a=1 HTTP/1.1" 200 120 "-" "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"',
        '203.0.113.101 - bob [01/Jan/2024:00:00:00 +0059] "PUT /minute-offset HTTP/1.1" 418 - "https://example.test/ref" "Agent With Spaces/1.0"',
    ]
    INVALID = [
        '203.0.113.102 - - [01/Jan/2024:00:00:00 +0060] "GET /bad-offset-minute HTTP/1.1" 200 1 "-" "Quoted/1.0"',
        '203.0.113.103 - - [01/Jan/2024:00:00:00 +0000] "GET /bad-status HTTP/1.1" 200.0 1 "-" "Quoted/1.0"',
        '203.0.113.104 - - [01/Jan/2024:00:00:00 +0000] "GET /bad-bytes HTTP/1.1" 200 10KB "-" "Quoted/1.0"',
    ]

    def setup_method(self):
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.VALID + self.INVALID:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.EXTRA):
            os.unlink(self.EXTRA)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_quoted_fields_and_numeric_edges(self):
        """Quoted fields with spaces are accepted while bad numerics are rejected."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.INVALID)
        assert r["error_requests"] == BASE_ERROR_REQUESTS + 1
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 120

        assert r["status_breakdown"]["2xx"] == 10
        assert r["status_breakdown"]["4xx"] == 4
        assert r["methods_breakdown"]["GET"] == 12
        assert r["methods_breakdown"]["PUT"] == 2

        assert r["hourly_requests"].get("00") == 1
        assert r["hourly_requests"].get("23") == 1


class TestRegularFilesAndLineEndings:
    EXTRA = "/app/logs/yy_crlf_quoted.log"
    LINK = "/app/logs/zz_symlink_payload.log"
    TARGET = "/app/logs/symlink_payload.txt"

    VALID = [
        '203.0.113.150 - - [02/Jan/2024:00:30:00 +0030] "GET /crlf?x=1 HTTP/1.1" 200 17 "https://example.test/a page" "Agent Name With Spaces/2.0"',
        '203.0.113.151 ident user [02/Jan/2024:00:00:00 -0130] "POST /crlf HTTP/1.1" 500 23 "referer with spaces" "Another Agent/3.0"',
    ]
    INVALID = [
        "not even close to a clf line",
    ]

    def setup_method(self):
        with open(self.EXTRA, "wb") as fh:
            for line in self.VALID + ["\t "] + self.INVALID:
                fh.write(line.encode("utf-8") + b"\r\n")
        with open(self.TARGET, "w", encoding="utf-8") as fh:
            fh.write(
                '203.0.113.199 - - [02/Jan/2024:00:00:00 +0000] '
                '"GET /symlink-trap HTTP/1.1" 200 999999 "-" "Trap/1.0"\n'
            )
        if os.path.lexists(self.LINK):
            os.unlink(self.LINK)
        os.symlink(self.TARGET, self.LINK)

    def teardown_method(self):
        for filename in (self.EXTRA, self.LINK, self.TARGET):
            if os.path.lexists(filename):
                os.unlink(filename)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_regular_files_crlf_and_quoted_spacing(self):
        """CRLF input is parsed and symlinked log names are ignored."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.INVALID)
        assert r["error_requests"] == BASE_ERROR_REQUESTS + 1
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 40

        assert r["status_breakdown"]["2xx"] == 10
        assert r["status_breakdown"]["5xx"] == 2
        assert r["methods_breakdown"]["GET"] == 12
        assert r["methods_breakdown"]["POST"] == 3

        assert r["hourly_requests"].get("00") == 1
        assert r["hourly_requests"].get("01") == 1
        assert all(entry["url"] != "/symlink-trap" for entry in r["top_urls_by_requests"])
        assert all(entry["ip"] != "203.0.113.199" for entry in r["top_ips_by_bytes"])


class TestQuotedEnvelopeAndTimestampEdges:
    EXTRA = "/app/logs/cc_envelope_time_edges.log"

    VALID = [
        '198.51.100.60 - - [01/Jan/2024:00:00:00 +0001] "GET /minute-back?x=1 HTTP/1.1" 200 10 "" ""',
        '198.51.100.61 ident user [31/Dec/2024:23:59:59 -0001] "POST /minute-forward HTTP/1.1" 201 20 "-" "Agent/1.0"',
        '198.51.100.62 - - [01/Mar/2400:00:00:00 +0000] "GET /far-leap HTTP/1.1" 204 30 "-" "Agent/1.0"',
    ]
    INVALID = [
        '198.51.100.63 - - [01/Jan/2024:00:00:00 +0000] "GET /extra HTTP/1.1" 200 1 "-" "Agent/1.0" trailing',
        '198.51.100.64 - - [01/Jan/2024:00:00:00 +0000] "GET /referer HTTP/1.1" 200 1 - "Agent/1.0"',
        '198.51.100.65 - - [01/Jan/2024:00:00:00 +0000] "GET /agent HTTP/1.1" 200 1 "-" Agent/1.0',
        '198.51.100.66 - - [01/jan/2024:00:00:00 +0000] "GET /month-case HTTP/1.1" 200 1 "-" "Agent/1.0"',
        '198.51.100.67 - - [00/Jan/2024:00:00:00 +0000] "GET /day-zero HTTP/1.1" 200 1 "-" "Agent/1.0"',
        '198.51.100.68 - - [29/Feb/2100:00:00:00 +0000] "GET /century HTTP/1.1" 200 1 "-" "Agent/1.0"',
        '198.51.100.69 - - [01/Jan/2024:00:00:00 0000] "GET /zone-sign HTTP/1.1" 200 1 "-" "Agent/1.0"',
    ]

    def setup_method(self):
        with open(self.EXTRA, "w", encoding="utf-8") as fh:
            for line in self.VALID + self.INVALID:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.EXTRA):
            os.unlink(self.EXTRA)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_quoted_envelope_and_timestamp_edges(self):
        """Malformed quote envelopes and impossible calendar dates are rejected."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + len(self.VALID)
        assert r["invalid_count"] == BASE_INVALID_COUNT + len(self.INVALID)
        assert r["error_requests"] == BASE_ERROR_REQUESTS
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 60

        assert r["status_breakdown"]["2xx"] == 12
        assert r["methods_breakdown"]["GET"] == 13
        assert r["methods_breakdown"]["POST"] == 3

        assert r["hourly_requests"].get("23") == 1
        assert r["hourly_requests"].get("00") == 2
        assert all("?" not in e["url"] for e in r["top_urls_by_requests"])


class TestHiddenRegularFileAndSparseCorpus:
    def setup_method(self):
        self.token = uuid.uuid4().hex[:8]
        self.hold = f"/app/logs/.hold_hidden_{self.token}"
        self.hidden = f"/app/logs/.hidden_{self.token}.log"
        self.visible = f"/app/logs/visible_sparse_{self.token}.log"
        os.makedirs(self.hold, exist_ok=True)
        self.moved = []
        for name in os.listdir("/app/logs"):
            src = os.path.join("/app/logs", name)
            if os.path.isfile(src) and name.endswith(".log"):
                dst = os.path.join(self.hold, name)
                os.rename(src, dst)
                self.moved.append((src, dst))

        with open(self.hidden, "w", encoding="utf-8") as fh:
            fh.write(
                '203.0.113.210 - - [01/Feb/2024:12:00:00 +0000] '
                '"GET /hidden?a=1 HTTP/1.1" 200 5 "-" "Hidden/1.0"\n'
            )
            fh.write(
                '203.0.113.211 - - [01/Feb/2024:12:30:00 +0000] '
                '"GET /hidden?a=2 HTTP/1.1" 404 7 "-" "Hidden/1.0"'
            )
        with open(self.visible, "w", encoding="utf-8") as fh:
            fh.write("\n \t \n")
            fh.write(
                '203.0.113.212 - - [01/Feb/2024:12:45:00 +0000] '
                '"GET /ignored HTTP/1.1" 99 1 "-" "Hidden/1.0"\n'
            )

    def teardown_method(self):
        for filename in (self.hidden, self.visible):
            if os.path.exists(filename):
                os.unlink(filename)
        for src, dst in reversed(self.moved):
            if os.path.exists(dst):
                os.rename(dst, src)
        if os.path.isdir(self.hold):
            os.rmdir(self.hold)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_hidden_regular_log_and_no_trailing_newline(self):
        """Hidden regular log files and final lines without newlines are processed."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == 2
        assert r["invalid_count"] == 1
        assert r["error_requests"] == 1
        assert r["total_bytes_transferred"] == 12
        assert r["status_breakdown"] == {
            "1xx": 0,
            "2xx": 1,
            "3xx": 0,
            "4xx": 1,
            "5xx": 0,
        }
        assert r["methods_breakdown"] == {"GET": 2}
        assert r["top_ips_by_bytes"] == [
            {"ip": "203.0.113.211", "bytes": 7},
            {"ip": "203.0.113.210", "bytes": 5},
        ]
        assert r["top_urls_by_requests"] == [
            {"url": "/hidden", "requests": 2},
        ]
        assert r["hourly_requests"] == {"12": 2}


class TestNoValidEntries:
    def setup_method(self):
        self.token = uuid.uuid4().hex[:8]
        self.hold = f"/app/logs/.hold_empty_{self.token}"
        self.extra = f"/app/logs/only_invalid_{self.token}.log"
        os.makedirs(self.hold, exist_ok=True)
        self.moved = []
        for name in os.listdir("/app/logs"):
            src = os.path.join("/app/logs", name)
            if os.path.isfile(src) and name.endswith(".log"):
                dst = os.path.join(self.hold, name)
                os.rename(src, dst)
                self.moved.append((src, dst))

        with open(self.extra, "w", encoding="utf-8") as fh:
            fh.write("   \n")
            fh.write('bad line with enough words but no fields\n')
            fh.write(
                '198.51.100.80 - - [01/Jan/2024:00:00:00 +0000] '
                '"GET /bad HTTP/1.1" 600 1 "-" "Empty/1.0"\n'
            )

    def teardown_method(self):
        if os.path.exists(self.extra):
            os.unlink(self.extra)
        for src, dst in reversed(self.moved):
            if os.path.exists(dst):
                os.rename(dst, src)
        if os.path.isdir(self.hold):
            os.rmdir(self.hold)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_report_shape_when_all_nonblank_lines_are_invalid(self):
        """A corpus with no valid entries still produces the full empty report."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()

        assert r["total_requests"] == 0
        assert r["invalid_count"] == 2
        assert r["error_requests"] == 0
        assert r["total_bytes_transferred"] == 0
        assert r["status_breakdown"] == {
            "1xx": 0,
            "2xx": 0,
            "3xx": 0,
            "4xx": 0,
            "5xx": 0,
        }
        assert r["methods_breakdown"] == {}
        assert r["top_ips_by_bytes"] == []
        assert r["top_urls_by_requests"] == []
        assert r["hourly_requests"] == {}


class TestRankingPressureInput:
    def setup_method(self):
        self.token = uuid.uuid4().hex[:8]
        self.extra = f"/app/logs/pp_rank_pressure_{self.token}.log"
        t = self.token
        valid = [
            f'198.51.200.2 - - [01/Jun/2024:00:00:00 +0000] "GET /rank-b-{t}?q=1 HTTP/1.1" 200 9000 "-" "Rank/1.0"',
            f'198.51.200.10 - - [01/Jun/2024:00:30:00 +0000] "POST /rank-b-{t}?q=2 HTTP/1.1" 201 4000 "-" "Rank/1.0"',
            f'198.51.200.10 - - [01/Jun/2024:01:00:00 +0000] "GET /rank-a-{t}?q=1 HTTP/1.1" 302 5000 "-" "Rank/1.0"',
            f'198.51.200.1 - - [01/Jun/2024:02:00:00 +0000] "DELETE /rank-a-{t}?q=2 HTTP/1.1" 404 8500 "-" "Rank/1.0"',
            f'198.51.200.20 - - [01/Jun/2024:03:00:00 +0000] "PUT /rank-c-{t}?q=1 HTTP/1.1" 500 8000 "-" "Rank/1.0"',
            f'198.51.200.3 - - [01/Jun/2024:04:00:00 +0000] "GET /rank-c-{t}?q=2 HTTP/1.1" 599 8000 "-" "Rank/1.0"',
            f'198.51.200.30 - - [01/Jun/2024:05:00:00 +0000] "GET /rank-d-{t} HTTP/1.1" 100 7999 "-" "Rank/1.0"',
            f'198.51.200.40 - - [01/Jun/2024:06:00:00 +0000] "GET /rank-a-{t}?q=3 HTTP/1.1" 204 1 "-" "Rank/1.0"',
            f'198.51.200.41 - - [01/Jun/2024:07:00:00 +0000] "POST /rank-a-{t}?q=4 HTTP/1.1" 204 1 "-" "Rank/1.0"',
            f'198.51.200.42 - - [01/Jun/2024:08:00:00 +0000] "POST /rank-b-{t}?q=3 HTTP/1.1" 204 1 "-" "Rank/1.0"',
            f'198.51.200.43 - - [01/Jun/2024:09:00:00 +0000] "POST /rank-b-{t}?q=4 HTTP/1.1" 204 1 "-" "Rank/1.0"',
            f'198.51.200.44 - - [01/Jun/2024:10:00:00 +0000] "PATCH /rank-c-{t}?q=3 HTTP/1.1" 204 1 "-" "Rank/1.0"',
        ]
        invalid = [
            f'198.51.200.50 - - [01/Jun/2024:00:00:00 +0000] "GET /bad-{t} HTTP/1.1" 600 1 "-" "Rank/1.0"',
            f'198.51.200.51 - - [01/Jun/2024:00:00:00 +0000] "GET /bad-{t} HTTP/1.1" 200 -- "-" "Rank/1.0"',
            f'198.51.200.52 - - [01/Jun/2024:00:00:00 +0000] "GET\t/bad-{t} HTTP/1.1" 200 1 "-" "Rank/1.0"',
        ]
        with open(self.extra, "w", encoding="utf-8") as fh:
            for line in valid + invalid:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.extra):
            os.unlink(self.extra)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_rankings_are_by_their_own_measures(self):
        """Independent ranking measures and tie breaks hold under a larger mix."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()
        t = self.token

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + 12
        assert r["invalid_count"] == BASE_INVALID_COUNT + 3
        assert r["error_requests"] == BASE_ERROR_REQUESTS + 3
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 50504

        assert r["status_breakdown"] == {
            "1xx": 1,
            "2xx": 16,
            "3xx": 3,
            "4xx": 4,
            "5xx": 3,
        }
        assert r["methods_breakdown"]["GET"] == 16
        assert r["methods_breakdown"]["POST"] == 6
        assert r["methods_breakdown"]["DELETE"] == 2
        assert r["methods_breakdown"]["PUT"] == 2
        assert r["methods_breakdown"]["PATCH"] == 1

        assert r["top_ips_by_bytes"] == [
            {"ip": "198.51.200.10", "bytes": 9000},
            {"ip": "198.51.200.2", "bytes": 9000},
            {"ip": "198.51.200.1", "bytes": 8500},
            {"ip": "198.51.200.20", "bytes": 8000},
            {"ip": "198.51.200.3", "bytes": 8000},
        ]
        assert r["top_urls_by_requests"] == [
            {"url": f"/rank-a-{t}", "requests": 4},
            {"url": f"/rank-b-{t}", "requests": 4},
            {"url": "/index.html", "requests": 3},
            {"url": f"/rank-c-{t}", "requests": 3},
            {"url": "/admin", "requests": 2},
        ]

        assert r["hourly_requests"].get("00") == 2
        assert r["hourly_requests"].get("02") == 6
        assert r["hourly_requests"].get("08") == 11
        assert r["hourly_requests"].get("10") == 1


class TestGeneratedMatrixInput:
    def setup_method(self):
        self.token = uuid.uuid4().hex[:8]
        self.extra = f"/app/logs/nn_matrix_{self.token}.log"
        t = self.token
        valid = [
            f'198.18.0.10 - - [15/Apr/2024:15:00:00 +0215] "GET /m-{t}?a=1 HTTP/1.1" 201 7000 "-" "Matrix/1.0"',
            f'198.18.0.10 - - [15/Apr/2024:00:30:00 -0145] "POST /m-{t}?a=2 HTTP/1.1" 404 3 "-" "Matrix/1.0"',
            f'198.18.0.2 - - [15/Apr/2024:23:05:00 -0210] "GET /n-{t} HTTP/1.1" 302 7000 "-" "Matrix/1.0"',
            f'198.18.0.11 - - [15/Apr/2024:01:00:00 +0000] "DELETE /z-{t}?q=1 HTTP/1.1" 500 7000 "-" "Matrix/1.0"',
            f'198.18.0.12 - - [15/Apr/2024:01:59:00 +0200] "GET /z-{t}?q=2 HTTP/1.1" 204 1 "-" "Matrix/1.0"',
            f'198.18.0.13 - - [15/Apr/2024:00:00:00 +0000] "GET /z-{t}?q=3 HTTP/1.1" 204 1 "-" "Matrix/1.0"',
        ]
        invalid = [
            f'198.18.0.14 - - [15/Apr/2024:00:00:00 +0000] "GET /bad-{t} HTTP/1.1" abc 1 "-" "Matrix/1.0"',
            f'198.18.0.15 - - [15/Apr/2024:00:00:00 +0000] "GET /bad-{t} HTTP/1.1" 200 +1 "-" "Matrix/1.0"',
            f'198.18.0.16 - - [29/Feb/2023:00:00:00 +0000] "GET /bad-{t} HTTP/1.1" 200 1 "-" "Matrix/1.0"',
            f'198.18.0.17 - - [15/Apr/2024:00:00:00 +0000] "GET  /bad-{t} HTTP/1.1" 200 1 "-" "Matrix/1.0"',
        ]
        with open(self.extra, "w", encoding="utf-8") as fh:
            for line in valid + invalid:
                fh.write(line + "\n")

    def teardown_method(self):
        if os.path.exists(self.extra):
            os.unlink(self.extra)
        subprocess.run(
            ["node", "/app/dist/index.js"],
            capture_output=True, check=False,
        )

    def test_generated_matrix(self):
        """A generated matrix combines parsing, UTC conversion, and rankings."""
        assert os.path.isfile("/app/dist/index.js"), "/app/dist/index.js was not built"

        r = rerun_report()
        t = self.token

        assert r["total_requests"] == BASE_TOTAL_REQUESTS + 6
        assert r["invalid_count"] == BASE_INVALID_COUNT + 4
        assert r["error_requests"] == BASE_ERROR_REQUESTS + 2
        assert r["total_bytes_transferred"] == BASE_TOTAL_BYTES + 21005

        assert r["status_breakdown"] == {
            "1xx": 0,
            "2xx": 12,
            "3xx": 3,
            "4xx": 4,
            "5xx": 2,
        }
        assert r["methods_breakdown"]["GET"] == 15
        assert r["methods_breakdown"]["POST"] == 3
        assert r["methods_breakdown"]["DELETE"] == 2

        assert r["hourly_requests"].get("12") == 1
        assert r["hourly_requests"].get("02") == 6
        assert r["hourly_requests"].get("01") == 2
        assert r["hourly_requests"].get("23") == 1
        assert r["hourly_requests"].get("00") == 1

        assert r["top_ips_by_bytes"][:3] == [
            {"ip": "198.18.0.10", "bytes": 7003},
            {"ip": "198.18.0.11", "bytes": 7000},
            {"ip": "198.18.0.2", "bytes": 7000},
        ]
        z_url = next((e for e in r["top_urls_by_requests"] if e["url"] == f"/z-{t}"), None)
        assert z_url == {"url": f"/z-{t}", "requests": 3}
        assert all("?" not in e["url"] for e in r["top_urls_by_requests"])
