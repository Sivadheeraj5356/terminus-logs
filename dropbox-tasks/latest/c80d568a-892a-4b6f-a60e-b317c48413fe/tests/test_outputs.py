"""Verifier for zeckendorf-fibonacci-coder-build.

30 ZKDF-framed fixtures. Each frame is (4-magic, LE-u64 salt, 1
variant marker, JSON tail); the driver XORs `salt & 0x7FFFFFFFFFFFFFFF`
into the parsed integer and runs Zeckendorf decomposition + a
variant-aware Fibonacci codeword, Elias-gamma companion, Miller-Rabin
primality, and golden-ratio bracketing on the result. Six independent
proof planes converge: chain_sha256 over per-entry canonical SHAs plus
the five witnesses (codeword, policy, roundtrip, salt, variant);
salt_witness over raw frame-header records including the variant
marker byte; variant_witness over the sorted per-entry {name, variant}
projection; policy_witness over the live runtime policy file;
roundtrip_witness over the per-entry decoder-side
{bit_len, name, roundtrip_ok} projection derived by composing
fibonacci_decode with zeckendorf_sum; codeword_witness over the
per-entry {name, ones_count, tail_bit} structural-shape projection.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
from pathlib import Path

import pytest


SRC_DIR = Path("/app/src/src")
FIXTURES_DIR = Path("/app/src/fixtures")
BINARY = Path("/app/src/target/release/zeckendorf-encode")
RESULTS = Path("/app/src/results.json")
POLICY_PATH = Path("/app/config/zeckendorf_policy.json")
CARGO_TOML = Path("/app/src/Cargo.toml")
EXPECTED_COHORT = "INC-2026-ZF1"
CAP_MIN = 1
CAP_MAX = 65536


EXPECTED_ENTRY_SHA = {
    "fx01": "4da2f5d10f15cde722308aadfc7bd6a51b8b77d6bbf0c0c2390dbcdf4a053166",
    "fx02": "43fe885cd3ed072c333cd21c1e7cb2b5ea8db7a80c546effbb0bfe830bfd8ff0",
    "fx03": "b504beed0411e90f43c3aa2ea073a00753f0cd53e7ac3ea36a8cf86eaa5ea512",
    "fx04": "dda7fbcf006d694f98f11a385e5c023b0a92b022c6f9532c83d06471d7c1813d",
    "fx05": "7785e26681ae08c361125829dfff95da202daad35138b828d8f158970d30d5ba",
    "fx06": "7e92d679ad0eceae7276409e2a7c5739b5d442dd9e0e107246414286bfff1446",
    "fx07": "778e85fe63176fcdccbc8d654cc9f7f5b79b5e3338bcc0f1a8885c1731e6234c",
    "fx08": "a28b6316c54c01685ec66c34df0794156a467fa7de949c7682d815c2bd09ef26",
    "fx09": "e3a84c56595960fe59fd49d4ab548204676bd3b385c7b43086f730601444aa1b",
    "fx10": "8cc3d4ff2a7b5c044e376bfd3628604daed5d6b5d39ef116711118a69f6e41d9",
    "fx11": "d43d66bcdd33e6a513e1761c27c4b9fd39eea57b7914eb773c74f637f7a2505a",
    "fx12": "4050ef0eef7f3d4a29fc930122d1ec41152dd24fe056a1b94107a23019a2c212",
    "fx13": "1bd8e57182035c38ad5f851fef320e443119a4afd71ea30ad19041dec8cd5906",
    "fx14": "5c0ea0e137fa6ce4b613594edaa61bfba99d38fff6c91dc776891b687c4ef001",
    "fx15": "84f27f90e5d3e6e4d778c5d02047f573788a9aa77493c7b97e9a3d0445e4eb98",
    "fx16": "c6a156c54955f96fa9d494323c58a26269190199c0ea702e1e6512e7e615cb66",
    "fx17": "4024faf95cdc9e9e97c557ac8e1c494c10a5df297b48234527a992bae374a40b",
    "fx18": "042809448c08719f6db9dd959c5c79d57342e3ac16694e0475ab2a749956500e",
    "fx19": "7e9e1cf4c9384710f34c0b7c5dee7c16d84ec96b53f83442e2281652005c7d6e",
    "fx20": "bd8f6dbf5a535f643d3dbeed5226aac855de3738d9c87db69134af008d10d7a0",
    "fx21": "1dbdb6c52b2e9645e70bf8f42674b63285339bf84cecd34bc11d15cefaefc4a5",
    "fx22": "8fb59d68ded1d08556e86ebaa6ea1f4961610b46c60d28dccb1f12706d3aca63",
    "fx23": "23920cffafc9b07bb903d8b1e27a0df37528ab3644d701d1f69dff471debc824",
    "fx24": "c35b965bf48e443fa62908f8bb17092c0beb225c277c0c16ff596dcb71160b6e",
    "fx25": "8210f63ec8ac4a3cb399fd8fa2be5f2a6946628db81f7b5a491b4bceff8e19df",
    "fx26": "5dfa969c8f783de70590614aaa4f2733199551dace50f6d1b60912cadd785438",
    "fx27": "5b94f881868b69fe8248db1e4b7994067c2cdb7cb2b18fc01239aa20d8eedd4e",
    "fx28": "7f3078a24428ebb1fa8afe7beebae63250927aa7dffaf5196ce3be37ebe698f4",
    "fx29": "96a28d984d0764d6f7d015a89f3c8abec1ea2c04d8d8e3cf038ebc8d5571fc68",
    "fx30": "6ef7952d1482ddf5b69d40a8c45d093494fd960f12b1bdf872ceefbacab95b53",
}

EXPECTED_CHAIN_SHA = "68128d7d7e2761b7ef402830eba56aa09a5a3ec436d0cf46d108ea4630e0cb1f"
EXPECTED_SALT_WITNESS = "e656e35a0d7927bb3ab5f4d1376620760de08fe673b78048c5a11c8a41a7e4d3"
EXPECTED_POLICY_WITNESS = "b5328cb1e629ba5389979190a7c1912f8b0f00c28ea25c3a283c6a2d60821229"
EXPECTED_VARIANT_WITNESS = "ee089abb0f22f09159c767d67ae85487723103f54e27a3fc53f61f1bae24f53e"
EXPECTED_ROUNDTRIP_WITNESS = "780efab9c960236f87fd8d58eded235162f2bba29cbdb8886c44dc5ff403da99"
EXPECTED_CODEWORD_WITNESS = "0dcbaf84caf285fd63419259e16801aaae195ad9c53d0b6ac97abe115eb906b2"
EXPECTED_WYTHOFF_WITNESS = "bd2cc2af1157dddb9536e396424e41e5d7ca072deb378920ced4c2392ef3e975"

EXPECTED_WITNESS = {
    "max_index": 92,
    "prime_count": 2,
    "prime_pi_100": 25,
    "total_bits": 1416,
    "total_elias_bits": 1918,
    "total_indices": 389,
    "total_ones": 417,
}

# Fixture stems declared with each variant marker byte.
CANONICAL_STEMS = {
    "fx01", "fx02", "fx03", "fx04", "fx05", "fx06", "fx07", "fx08",
    "fx09", "fx10", "fx26", "fx27", "fx28", "fx30",
}
REVERSE_MSB_STEMS = {
    "fx11", "fx12", "fx13", "fx14", "fx15", "fx16", "fx17", "fx18",
    "fx19", "fx20", "fx21", "fx22", "fx23", "fx24", "fx29",
}
UNKNOWN_STEMS = {"fx25"}
BAD_MAGIC_STEMS = {"fx26"}
ZERO_N_STEMS = BAD_MAGIC_STEMS | UNKNOWN_STEMS


def _canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@pytest.fixture(scope="session")
def results_json():
    """Load /app/src/results.json once per session."""
    assert RESULTS.is_file(), f"missing {RESULTS}"
    return json.loads(RESULTS.read_text())


def _entry(results_json, name):
    for e in results_json["decoded"]:
        if e["name"] == name:
            return e
    raise AssertionError(f"fixture {name} not present in results")


def test_binary_exists_and_executable():
    """The release binary /app/src/target/release/zeckendorf-encode is present + executable."""
    assert BINARY.is_file(), f"missing binary {BINARY}"
    assert os.access(BINARY, os.X_OK)


def test_results_json_is_canonical_bytes():
    """results.json is canonical byte-for-byte: sorted keys at every depth,
    no whitespace, no trailing newline."""
    raw = RESULTS.read_bytes()
    assert not raw.endswith(b"\n"), "trailing newline byte violates canonical JSON"
    obj = json.loads(raw)
    assert raw.decode() == _canonical(obj), "not canonical JSON"


def test_top_level_key_set_is_exact(results_json):
    """Top-level keys are exactly the nine documented scalars
    {chain_sha256, codeword_witness, decoded, policy_witness,
    roundtrip_witness, salt_witness, variant_witness, witness,
    wythoff_witness} — the 2026-07-10 wythoff_witness addendum grew
    the key set from eight to nine (`witness` still sorts before
    `wythoff_witness` because `wi` < `wy`)."""
    assert set(results_json.keys()) == {
        "chain_sha256", "codeword_witness", "decoded", "policy_witness",
        "roundtrip_witness", "salt_witness", "variant_witness", "witness",
        "wythoff_witness"
    }


def test_decoded_sorted_by_name(results_json):
    """decoded list is sorted ascending by name (fixture stem)."""
    names = [e["name"] for e in results_json["decoded"]]
    assert names == sorted(names)


def test_fixture_set_complete(results_json):
    """Every .json fixture in /app/src/fixtures appears in results.decoded."""
    expected = {p.stem for p in FIXTURES_DIR.glob("*.json")}
    got = {e["name"] for e in results_json["decoded"]}
    assert got == expected


def test_decoded_entry_shape(results_json):
    """Each entry has exactly the nine documented keys with correct types."""
    required = {"elias_gamma_code", "fibonacci_code", "is_prime", "n",
                "name", "phi_p", "phi_q", "variant", "zeckendorf"}
    for e in results_json["decoded"]:
        assert set(e.keys()) == required, e
        assert isinstance(e["fibonacci_code"], str)
        assert isinstance(e["elias_gamma_code"], str)
        assert isinstance(e["is_prime"], bool)
        assert isinstance(e["n"], int) and e["n"] >= 0
        assert isinstance(e["name"], str)
        assert isinstance(e["phi_p"], int) and e["phi_p"] >= 0
        assert isinstance(e["phi_q"], int) and e["phi_q"] >= 0
        assert isinstance(e["variant"], str)
        assert e["variant"] in {"canonical", "reverse-msb", "unknown"}
        assert isinstance(e["zeckendorf"], list)
        assert all(isinstance(k, int) and k >= 2 for k in e["zeckendorf"])


def test_zeckendorf_indices_sorted_ascending(results_json):
    """Each entry's zeckendorf list is sorted ascending."""
    for e in results_json["decoded"]:
        z = e["zeckendorf"]
        assert z == sorted(z), f"{e['name']}: zeckendorf not sorted: {z}"


def test_zeckendorf_indices_non_consecutive(results_json):
    """Zeckendorf's rule: no two chosen Fibonacci indices differ by 1."""
    for e in results_json["decoded"]:
        z = e["zeckendorf"]
        for a, b in zip(z, z[1:]):
            assert b - a >= 2, f"{e['name']}: consecutive indices {a},{b}"


def _fibonacci(k: int) -> int:
    """F_2 = 1, F_3 = 2, F_4 = 3, F_5 = 5, ... — the shipping convention."""
    a, b = 1, 2
    if k == 2:
        return a
    if k == 3:
        return b
    for _ in range(4, k + 1):
        a, b = b, a + b
    return b


def test_fibonacci_convention_pinned_values():
    """The shipping F_2 = 1 convention: F_2..F_10 must be
    1, 2, 3, 5, 8, 13, 21, 34, 55 per contracts §zeckendorf.md."""
    assert _fibonacci(2) == 1
    assert _fibonacci(3) == 2
    assert _fibonacci(4) == 3
    assert _fibonacci(5) == 5
    assert _fibonacci(6) == 8
    assert _fibonacci(7) == 13
    assert _fibonacci(8) == 21
    assert _fibonacci(9) == 34
    assert _fibonacci(10) == 55


def test_zeckendorf_sums_to_n(results_json):
    """For each entry, sum of F_k for k in zeckendorf equals n."""
    for e in results_json["decoded"]:
        s = sum(_fibonacci(k) for k in e["zeckendorf"])
        assert s == e["n"], f"{e['name']}: sum(F_k)={s} != n={e['n']}"


def _canonical_fibonacci_code(indices):
    """Reference canonical Fibonacci codeword — MSB-first."""
    if not indices:
        return ""
    max_k = max(indices)
    bits = ["0"] * max_k
    for k in indices:
        bits[k - 2] = "1"
    bits[max_k - 1] = "1"
    return "".join(bits)


def _variant_fibonacci_code(indices, variant):
    canonical = _canonical_fibonacci_code(indices)
    if variant == "reverse-msb":
        return canonical[::-1]
    return canonical


def test_fibonacci_code_matches_variant(results_json):
    """Fibonacci code matches the canonical / reverse-msb recipe per the
    entry's declared variant. Under reverse-msb the codeword is the
    canonical string reversed end-for-end (contracts §variants.md)."""
    for e in results_json["decoded"]:
        expected = _variant_fibonacci_code(e["zeckendorf"], e["variant"])
        assert e["fibonacci_code"] == expected, (
            f"{e['name']}: variant={e['variant']} code={e['fibonacci_code']!r} "
            f"expected {expected!r}"
        )


def test_fibonacci_code_length_matches_max_k(results_json):
    """Codeword length equals max(zeckendorf) for non-empty entries,
    zero otherwise — variant reversal preserves length."""
    for e in results_json["decoded"]:
        z = e["zeckendorf"]
        code = e["fibonacci_code"]
        if not z:
            assert code == "", f"{e['name']}: empty zeckendorf, non-empty code"
            continue
        assert len(code) == max(z), f"{e['name']}: len {len(code)} != max_k {max(z)}"


def _elias(n: int) -> str:
    """Elias-gamma per contracts §prefix_code.md — n=0 pins to '0'."""
    if n == 0:
        return "0"
    w = n.bit_length()
    return "0" * (w - 1) + bin(n)[2:]


def test_elias_gamma_layout(results_json):
    """Elias-gamma matches the reference recipe including the buried
    n=0 → '0' rule from contracts §prefix_code.md."""
    for e in results_json["decoded"]:
        expected = _elias(e["n"])
        assert e["elias_gamma_code"] == expected, (
            f"{e['name']}: elias {e['elias_gamma_code']!r} != {expected!r}"
        )


def test_elias_gamma_zero_pinned_to_single_bit(results_json):
    """The buried n=0 rule: elias_gamma_code is '0', not '' — asserted
    on every zero-n entry (bad magic + unknown variant)."""
    for stem in ZERO_N_STEMS:
        e = _entry(results_json, stem)
        assert e["n"] == 0
        assert e["elias_gamma_code"] == "0", (
            f"{stem}: elias_gamma_code {e['elias_gamma_code']!r} — the buried "
            f"n=0 rule pins this to '0' per contracts §prefix_code.md"
        )


@pytest.mark.parametrize("n_val,expected_code", [
    (0, "0"),
    (1, "1"),
    (2, "010"),
    (3, "011"),
    (4, "00100"),
    (5, "00101"),
    (10, "0001010"),
    (16, "000010000"),
])
def test_elias_gamma_table(n_val, expected_code):
    """Elias-gamma reference table including the n=0 buried rule."""
    assert _elias(n_val) == expected_code


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    for p in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if n == p:
            return True
        if n % p == 0:
            return False
    d = n - 1
    r = 0
    while d % 2 == 0:
        d //= 2
        r += 1
    for a in (2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37):
        if a >= n:
            continue
        x = pow(a, d, n)
        if x == 1 or x == n - 1:
            continue
        witnessed = False
        for _ in range(r - 1):
            x = pow(x, 2, n)
            if x == n - 1:
                witnessed = True
                break
        if not witnessed:
            return False
    return True


def test_is_prime_matches_reference(results_json):
    """Each entry's is_prime agrees with the reference primality test."""
    for e in results_json["decoded"]:
        assert e["is_prime"] == _is_prime(e["n"]), (
            f"{e['name']}: is_prime={e['is_prime']} for n={e['n']}"
        )


def test_is_prime_edge_cases_match_contract():
    """Buried edge-case rules from contracts §Primality:
    is_prime(0) == false, is_prime(1) == false, is_prime(2) == true."""
    assert _is_prime(0) is False
    assert _is_prime(1) is False
    assert _is_prime(2) is True


def test_fx28_effective_n_is_prime(results_json):
    """fx28 was constructed so salt XOR raw_n = 2017 (a prime); is_prime must be True."""
    e = _entry(results_json, "fx28")
    assert e["n"] == 2017
    assert e["is_prime"] is True


def test_phi_p_and_phi_q_are_consecutive_fibs(results_json):
    """phi_p == F_{max_k+1} and phi_q == F_{max_k} for non-empty entries; both 0 otherwise."""
    for e in results_json["decoded"]:
        if not e["zeckendorf"]:
            assert e["phi_p"] == 0 and e["phi_q"] == 0
            continue
        max_k = max(e["zeckendorf"])
        assert e["phi_q"] == _fibonacci(max_k), f"{e['name']}: phi_q mismatch"
        assert e["phi_p"] == _fibonacci(max_k + 1), f"{e['name']}: phi_p mismatch"
        if max_k > 2:
            assert e["phi_p"] == e["phi_q"] + _fibonacci(max_k - 1), (
                f"{e['name']}: recurrence broken"
            )


@pytest.mark.parametrize("fx,expected_sha", sorted(EXPECTED_ENTRY_SHA.items()))
def test_fixture_entry_canonical_sha(results_json, fx, expected_sha):
    """Each fixture's entry, canonical-JSON encoded, hashes to the expected SHA-256."""
    e = _entry(results_json, fx)
    entry_bytes = _canonical(e).encode()
    got = hashlib.sha256(entry_bytes).hexdigest()
    assert got == expected_sha, (
        f"{fx}: canonical entry sha mismatch — got {got}, expected {expected_sha}"
    )


def test_chain_sha256_matches_expected(results_json):
    """chain_sha256 matches the pinned aggregate hash for the 30 shipped fixtures."""
    assert results_json["chain_sha256"] == EXPECTED_CHAIN_SHA


def test_chain_sha256_recomputes(results_json):
    """chain_sha256 = SHA-256 of concat(per-entry canonical SHAs in
    decoded order || codeword_witness || policy_witness ||
    roundtrip_witness || salt_witness || variant_witness ||
    wythoff_witness). Witnesses append in lex order (codeword < policy
    < roundtrip < salt < variant < wythoff) per
    contracts/witnesses.md §chain_sha256."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(results_json["policy_witness"].encode())
    h.update(results_json["roundtrip_witness"].encode())
    h.update(results_json["salt_witness"].encode())
    h.update(results_json["variant_witness"].encode())
    h.update(results_json["wythoff_witness"].encode())
    assert results_json["chain_sha256"] == h.hexdigest()


def test_witness_matches_expected(results_json):
    """witness object matches the pinned semantic aggregates."""
    assert results_json["witness"] == EXPECTED_WITNESS


def test_witness_recomputes_from_decoded(results_json):
    """Every witness aggregate matches iteration over decoded — independent proof plane."""
    decoded = results_json["decoded"]
    total_bits = sum(len(e["fibonacci_code"]) for e in decoded)
    total_ones = sum(e["fibonacci_code"].count("1") for e in decoded)
    total_indices = sum(len(e["zeckendorf"]) for e in decoded)
    total_elias = sum(len(e["elias_gamma_code"]) for e in decoded)
    prime_count = sum(1 for e in decoded if e["is_prime"])
    max_index = max((max(e["zeckendorf"]) for e in decoded if e["zeckendorf"]), default=0)
    w = results_json["witness"]
    assert w["total_bits"] == total_bits
    assert w["total_ones"] == total_ones
    assert w["total_indices"] == total_indices
    assert w["total_elias_bits"] == total_elias
    assert w["prime_count"] == prime_count
    assert w["max_index"] == max_index


def test_witness_arithmetic_identity(results_json):
    """total_ones == total_indices + (count of non-empty codes) — Zeckendorf
    bit + terminating '1' per non-empty code. Holds under both variants
    since reverse-msb preserves the '1' count."""
    decoded = results_json["decoded"]
    nonempty = sum(1 for e in decoded if e["fibonacci_code"])
    w = results_json["witness"]
    assert w["total_ones"] == w["total_indices"] + nonempty


def test_prime_pi_100_is_25(results_json):
    """prime_pi(100) = 25 — a fixed invariant that exercises
    crate::primes::prime_pi at runtime. A stub prime_pi returning 0
    breaks this and, through chain_sha256, every downstream SHA."""
    assert results_json["witness"]["prime_pi_100"] == 25


def test_chain_sha256_lowercase_hex(results_json):
    """chain_sha256 is 64 lowercase-hex characters."""
    assert re.fullmatch(r"[0-9a-f]{64}", results_json["chain_sha256"])


def test_salt_witness_matches_expected(results_json):
    """salt_witness matches the pinned value derived from raw frame headers."""
    assert results_json["salt_witness"] == EXPECTED_SALT_WITNESS


def test_salt_witness_recomputes_from_raw_frames(results_json):
    """salt_witness is SHA-256 over canonical JSON of sorted
    [{magic_ok, name, salt, variant_marker}] records read directly from
    raw fixture bytes — an independent proof plane."""
    records = []
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        raw = path.read_bytes()
        assert len(raw) >= 13, f"{path.name}: frame under 13 bytes"
        magic = raw[:4]
        salt = struct.unpack("<Q", raw[4:12])[0]
        variant_marker = raw[12]
        records.append({
            "magic_ok": magic == b"ZKDF",
            "name": path.stem,
            "salt": salt,
            "variant_marker": variant_marker,
        })
    records.sort(key=lambda r: r["name"])
    computed = hashlib.sha256(_canonical(records).encode()).hexdigest()
    assert results_json["salt_witness"] == computed


def test_chain_uses_salt_xor(results_json):
    """For each ZKDF-magic fixture with known variant marker, entry.n
    must equal raw JSON n XOR (salt & 0x7FFFFFFFFFFFFFFF). Bad-magic
    fixtures and unknown-variant fixtures both zero to n = 0."""
    for path in sorted(FIXTURES_DIR.glob("*.json")):
        raw = path.read_bytes()
        magic = raw[:4]
        salt = struct.unpack("<Q", raw[4:12])[0]
        variant_marker = raw[12]
        tail = raw[13:].decode()
        raw_n = int(re.search(r'"n":\s*(\d+)', tail).group(1))
        e = _entry(results_json, path.stem)
        if magic == b"ZKDF" and variant_marker in (0x00, 0x01):
            assert e["n"] == raw_n ^ (salt & 0x7FFFFFFFFFFFFFFF), (
                f"{path.stem}: entry.n does not match XOR-derived effective n"
            )
        else:
            assert e["n"] == 0, (
                f"{path.stem}: bad-magic / unknown-variant must produce n=0"
            )


def test_bad_magic_produces_empty_entry(results_json):
    """fx26 has non-ZKDF magic — its entry must be the zero shape
    (with the buried elias_gamma '0' rule for n=0)."""
    e = _entry(results_json, "fx26")
    assert e["n"] == 0
    assert e["zeckendorf"] == []
    assert e["fibonacci_code"] == ""
    assert e["elias_gamma_code"] == "0"
    assert e["is_prime"] is False
    assert e["phi_p"] == 0 and e["phi_q"] == 0
    assert e["variant"] == "canonical"


def test_unknown_variant_produces_empty_entry(results_json):
    """fx25 has an unknown variant marker byte — its entry must be the
    zero shape with variant label 'unknown' per contracts §variants.md."""
    e = _entry(results_json, "fx25")
    assert e["n"] == 0
    assert e["zeckendorf"] == []
    assert e["fibonacci_code"] == ""
    assert e["elias_gamma_code"] == "0"
    assert e["is_prime"] is False
    assert e["phi_p"] == 0 and e["phi_q"] == 0
    assert e["variant"] == "unknown"


def test_fx27_salt_zero_is_invariant(results_json):
    """fx27 has salt=0, so n_effective must equal the raw JSON integer."""
    path = FIXTURES_DIR / "fx27.json"
    raw = path.read_bytes()
    salt = struct.unpack("<Q", raw[4:12])[0]
    assert salt == 0
    raw_n = int(re.search(r'"n":\s*(\d+)', raw[13:].decode()).group(1))
    e = _entry(results_json, "fx27")
    assert e["n"] == raw_n


def test_fx30_effective_n_is_large_fibonacci(results_json):
    """fx30 was constructed so n_effective equals a single large Fibonacci —
    Zeckendorf must be exactly one index and phi_q must equal n_effective."""
    e = _entry(results_json, "fx30")
    assert len(e["zeckendorf"]) == 1
    max_k = e["zeckendorf"][0]
    assert e["n"] == _fibonacci(max_k)
    assert e["phi_q"] == e["n"]


def test_chain_input_includes_new_fields(results_json):
    """A stale per-entry serializer that omits any of the new fields would
    change the SHA — this test asserts the entry canonical JSON literally
    contains every new key name (including the variant field added in
    2026-07-07)."""
    for e in results_json["decoded"]:
        canon = _canonical(e)
        for key in ("elias_gamma_code", "fibonacci_code", "is_prime", "n",
                    "name", "phi_p", "phi_q", "variant", "zeckendorf"):
            assert f'"{key}"' in canon, f"{e['name']}: canonical entry missing key {key!r}"


# ────────────────────────────────────────────────────────────────
# Live-config policy + policy_witness plane
# ────────────────────────────────────────────────────────────────

def test_policy_witness_lowercase_hex(results_json):
    """policy_witness is 64 lowercase-hex characters."""
    assert re.fullmatch(r"[0-9a-f]{64}", results_json["policy_witness"])


def test_policy_witness_recomputes_from_live_config_bytes(results_json):
    """policy_witness = SHA-256 over canonical JSON of
    {cohort, max_codeword_bits, policy_sha256, policy_witness_salt}
    where policy_sha256 = SHA-256 of the raw bytes of the live policy file."""
    assert POLICY_PATH.is_file(), f"missing {POLICY_PATH}"
    raw = POLICY_PATH.read_bytes()
    policy = json.loads(raw)
    policy_sha256 = hashlib.sha256(raw).hexdigest()
    witness_input = _canonical({
        "cohort": policy["cohort"],
        "max_codeword_bits": policy["max_codeword_bits"],
        "policy_sha256": policy_sha256,
        "policy_witness_salt": policy["policy_witness_salt"],
    })
    computed = hashlib.sha256(witness_input.encode()).hexdigest()
    assert results_json["policy_witness"] == computed


def test_policy_witness_participates_in_chain_sha256(results_json):
    """chain_sha256 depends on policy_witness — substituting a null-hex
    witness under an otherwise identical chain input yields a different
    hash. Proves the chain binds the runtime policy."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(("0" * 64).encode())  # perturb policy_witness
    h.update(results_json["roundtrip_witness"].encode())
    h.update(results_json["salt_witness"].encode())
    h.update(results_json["variant_witness"].encode())
    h.update(results_json["wythoff_witness"].encode())
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed, (
        "chain_sha256 unchanged when policy_witness is nulled"
    )


def test_policy_file_ships_with_expected_schema():
    """/app/config/zeckendorf_policy.json has exactly the three documented
    keys, cohort matches the compiled constant, and the cap is in range."""
    assert POLICY_PATH.is_file(), f"missing {POLICY_PATH}"
    raw = POLICY_PATH.read_text()
    policy = json.loads(raw)
    assert set(policy.keys()) == {"cohort", "max_codeword_bits", "policy_witness_salt"}
    assert policy["cohort"] == EXPECTED_COHORT
    cap = policy["max_codeword_bits"]
    assert isinstance(cap, int) and CAP_MIN <= cap <= CAP_MAX


def test_binary_reads_policy_on_every_invocation(tmp_path):
    """Mutate the live policy to a cap tighter than any shipped fixture's
    fibonacci_code length, invoke the binary against a fresh output path,
    and expect a CodewordLengthCap rejection with a non-zero exit."""
    assert BINARY.is_file(), f"missing binary {BINARY}"
    original = POLICY_PATH.read_bytes()
    try:
        POLICY_PATH.write_text(
            '{"cohort":"' + EXPECTED_COHORT + '","max_codeword_bits":30,'
            '"policy_witness_salt":"2026-07-06"}'
        )
        out = tmp_path / "cap.json"
        proc = subprocess.run(
            [str(BINARY), "--fixtures", str(FIXTURES_DIR), "--out", str(out)],
            capture_output=True, text=True, timeout=60,
        )
        assert proc.returncode != 0, (
            f"expected non-zero exit for cap violation, got {proc.returncode}"
        )
        combined = (proc.stdout + proc.stderr)
        assert "CodewordLengthCap" in combined, (
            f"stderr/stdout missing CodewordLengthCap token:\n{combined}"
        )
    finally:
        POLICY_PATH.write_bytes(original)


# ────────────────────────────────────────────────────────────────
# variant_witness (2026-07-07 addendum)
# ────────────────────────────────────────────────────────────────


def test_variant_witness_hex_shape(results_json):
    """variant_witness is 64 lowercase hex chars."""
    assert "variant_witness" in results_json
    v = results_json["variant_witness"]
    assert re.fullmatch(r"[0-9a-f]{64}", v), v


def test_variant_witness_matches_expected(results_json):
    """variant_witness matches the pinned value on the shipped corpus."""
    assert results_json["variant_witness"] == EXPECTED_VARIANT_WITNESS


def test_variant_witness_recomputes_from_decoded(results_json):
    """variant_witness = SHA-256(canonical_json(sorted [{name, variant}]))
    per contracts §variants.md."""
    projection = []
    for e in sorted(results_json["decoded"], key=lambda x: x["name"]):
        projection.append({"name": e["name"], "variant": e["variant"]})
    computed = hashlib.sha256(_canonical(projection).encode()).hexdigest()
    assert computed == results_json["variant_witness"], (
        "variant_witness does not match SHA-256 of canonical JSON over "
        "sorted per-fixture {name, variant} projection"
    )


def test_variant_witness_participates_in_chain_sha256(results_json):
    """Perturbing variant_witness in the chain input changes chain_sha256.
    A decoder that leaves variant_witness out of chain input fails here."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(results_json["policy_witness"].encode())
    h.update(results_json["roundtrip_witness"].encode())
    h.update(results_json["salt_witness"].encode())
    h.update(("0" * 64).encode())  # perturb variant_witness
    h.update(results_json["wythoff_witness"].encode())
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed, (
        "chain_sha256 unchanged when variant_witness is nulled — the "
        "plane does not feed into the chain hash"
    )


def test_variants_contract_ships():
    """docs/contracts/variants.md exists and names both variants + the
    variant_witness formula."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "variants.md"
    assert contract.is_file(), "docs/contracts/variants.md missing"
    text = contract.read_text()
    for marker in ("canonical", "reverse-msb", "0x00", "0x01",
                   "VariantUnknown", "variant_witness"):
        assert marker in text, f"variants.md missing '{marker}'"


def test_rejections_contract_lists_variant_unknown():
    """rejections.md ships the VariantUnknown variant added by the
    2026-07-07 variants addendum."""
    text = (SRC_DIR.parent / "docs" / "contracts" / "rejections.md").read_text()
    assert "VariantUnknown" in text, (
        "rejections.md missing VariantUnknown; agents cannot spell the "
        "variant correctly without seeing it named in the contracts"
    )


def test_variants_declared_by_fixture(results_json):
    """The declared variant labels match the per-fixture marker byte
    partition: fx25 unknown, fx26+fx01-fx10+fx27+fx28+fx30 canonical,
    fx11-fx24+fx29 reverse-msb."""
    seen_canonical = set()
    seen_reverse = set()
    seen_unknown = set()
    for e in results_json["decoded"]:
        if e["variant"] == "canonical":
            seen_canonical.add(e["name"])
        elif e["variant"] == "reverse-msb":
            seen_reverse.add(e["name"])
        elif e["variant"] == "unknown":
            seen_unknown.add(e["name"])
    assert seen_canonical == CANONICAL_STEMS, (
        f"canonical set drift: got {seen_canonical}, expected {CANONICAL_STEMS}"
    )
    assert seen_reverse == REVERSE_MSB_STEMS, (
        f"reverse-msb set drift: got {seen_reverse}, expected {REVERSE_MSB_STEMS}"
    )
    assert seen_unknown == UNKNOWN_STEMS, (
        f"unknown set drift: got {seen_unknown}, expected {UNKNOWN_STEMS}"
    )


def test_reverse_msb_bit_reversal_pointwise(results_json):
    """Under reverse-msb the emitted codeword is the canonical string
    reversed end-for-end — pointwise check against the reference
    canonical layout."""
    for e in results_json["decoded"]:
        if e["variant"] != "reverse-msb":
            continue
        canonical = _canonical_fibonacci_code(e["zeckendorf"])
        assert e["fibonacci_code"] == canonical[::-1], (
            f"{e['name']}: reverse-msb code {e['fibonacci_code']!r} is not "
            f"the reverse of canonical {canonical!r}"
        )


def test_canonical_and_reverse_msb_have_same_length(results_json):
    """Variant reversal preserves length — a decoder that emits reversed
    bits should still produce max_k-length codewords."""
    for e in results_json["decoded"]:
        if not e["zeckendorf"]:
            continue
        assert len(e["fibonacci_code"]) == max(e["zeckendorf"])


# ────────────────────────────────────────────────────────────────
# Decoy + anti-cheat + module-split invariants
# ────────────────────────────────────────────────────────────────


_ALGO_MODULES = (
    "fibonacci.rs",
    "zeckendorf.rs",
    "fibonacci_code.rs",
    "elias_gamma.rs",
    "primes.rs",
)


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def test_decoy_module_not_on_decode_path():
    """The `decoy` module ships out-of-scope stubs — `lib.rs`, `main.rs`,
    and `json.rs` must not reference any decoy-only symbol (`NegaError`,
    `MAX_NEG_INDEX`, `decode_signed`, `encode_signed`). The
    `crate::negafibonacci` real module IS on the crate surface and IS
    referenced by main.rs (for the `negafib --n <int>` subcommand), so
    the `negafibonacci` needle is intentionally NOT in this scan — see
    `test_negafibonacci_module_declared_in_lib` for that check."""
    lib_text = _strip_comments((SRC_DIR / "lib.rs").read_text())
    lib_no_mod = re.sub(r"pub\s+mod\s+decoy\s*;", "", lib_text)
    for needle in ("MAX_NEG_INDEX", "NegaError",
                   "decode_signed", "encode_signed"):
        assert needle not in lib_no_mod, (
            f"lib.rs references decoy symbol {needle!r} on the decode path"
        )
    for path in (SRC_DIR / "main.rs", SRC_DIR / "json.rs"):
        text = _strip_comments(path.read_text())
        for needle in ("decoy", "NegaError", "MAX_NEG_INDEX"):
            assert needle not in text, (
                f"{path.name} references decoy symbol {needle!r}"
            )


def test_all_five_algorithmic_modules_exist():
    """The 2026-07-07 rotation split lib.rs into five per-concern modules.
    Every module MUST ship as a source file under /app/src/src/."""
    for m in _ALGO_MODULES:
        assert (SRC_DIR / m).is_file(), (
            f"module {m} missing from /app/src/src/ — the algorithmic surface "
            f"is split per docs/INCIDENT_LOG.md 2026-07-07 addendum"
        )


def test_no_todo_stubs_across_all_algorithmic_modules():
    """Every algorithmic module must have its `todo!()` stub replaced by
    a real implementation. lib.rs is checked separately."""
    for m in _ALGO_MODULES:
        src = _strip_comments((SRC_DIR / m).read_text())
        assert "todo!" not in src, f"{m} still contains a todo!() stub"
        assert "unimplemented!" not in src, (
            f"{m} still contains an unimplemented!() stub"
        )


def test_no_todo_stubs_remain():
    """lib.rs no longer contains any todo!() macro."""
    text = _strip_comments((SRC_DIR / "lib.rs").read_text())
    assert "todo!" not in text, "lib.rs still contains a todo!()"


def test_algorithmic_module_source_size_floors():
    """Every algorithmic module has a minimum byte-size floor calibrated
    at ~55% of the reference implementation (bumped ~15% from the
    earlier 40% band) so a stubby `pub fn f() -> _ { Default::default() }`
    empty body can't clear it and the module-split hardening survives
    the recollapse pattern."""
    floors = {
        "fibonacci.rs":       320,
        "zeckendorf.rs":      440,
        "fibonacci_code.rs": 1035,
        "elias_gamma.rs":     440,
        "primes.rs":          690,
    }
    for name, floor in floors.items():
        actual = (SRC_DIR / name).stat().st_size
        assert actual >= floor, f"{name} is {actual} bytes; floor {floor}"


def test_fibonacci_constants_not_hardcoded_in_zeckendorf_module():
    """zeckendorf.rs must NOT hardcode Fibonacci values above F_3 = 2 as
    literal integers. Every Fibonacci lookup must go through
    crate::fibonacci::fibonacci. Copy-pasting a
    [1, 2, 3, 5, 8, 13, 21, ...] lookup table trips this test."""
    text = _strip_comments((SRC_DIR / "zeckendorf.rs").read_text())
    # Strip string literals so a code fence in a docstring/comment
    # is not counted (comments are already stripped, but defensively
    # strip strings too).
    text = re.sub(r'"([^"\\]|\\.)*"', "", text)
    # Fibonacci values above F_3 = 2. Any of these appearing in
    # zeckendorf.rs is a hardcode signal.
    forbidden = ["144", "233", "377", "610", "987", "1597", "2584", "4181",
                 "6765", "10946", "17711", "28657"]
    hits = []
    for lit in forbidden:
        # Word-boundary match so incidental substrings are not
        # counted (e.g. 233 inside 12233).
        if re.search(rf"(?<!\d){lit}(?!\d)", text):
            hits.append(lit)
    assert not hits, (
        f"zeckendorf.rs contains hardcoded Fibonacci literal(s) {hits} — "
        f"every Fibonacci lookup MUST go through crate::fibonacci::fibonacci "
        f"per contracts §Do not hardcode."
    )


def test_zeckendorf_module_imports_fibonacci():
    """zeckendorf.rs must import from crate::fibonacci — the module split
    forces the dependency edge and this test surfaces the miss statically."""
    text = (SRC_DIR / "zeckendorf.rs").read_text()
    assert re.search(r"use\s+crate::fibonacci::", text) or \
           re.search(r"crate::fibonacci::fibonacci", text) or \
           re.search(r"crate::fibonacci::fib_index_of", text), (
        "zeckendorf.rs does not reference crate::fibonacci — the greedy "
        "MUST call fibonacci() from the fibonacci module, not inline"
    )


def test_no_external_num_crate():
    """No external number-theory / big-int / primality crate in Cargo.toml."""
    cargo = CARGO_TOML.read_text()
    for term in ("num-bigint", "num-traits", "rug", "malachite",
                 "fibonacci_codec", "primal", "miller_rabin", "is_prime"):
        assert term not in cargo, f"Cargo.toml references forbidden crate {term!r}"


def test_no_hardcoded_sha256_in_algorithmic_modules():
    """No 64-char hex string literal in any algorithmic module (would be a
    hardcoded answer-table cheat). lib.rs also included."""
    for m in ("lib.rs",) + _ALGO_MODULES:
        text = _strip_comments((SRC_DIR / m).read_text())
        assert not re.search(r'"[0-9a-f]{64}"', text), (
            f"{m} contains a 64-char hex string literal"
        )


def test_no_fixture_n_literals_in_algorithmic_modules():
    """No fixture-derived numeric literal (like the max u64 salt or a
    specific fixture's n_effective) in any algorithmic module."""
    for m in ("lib.rs",) + _ALGO_MODULES:
        text = _strip_comments((SRC_DIR / m).read_text())
        forbidden = ["12586269025", "9223372036854775806",
                     "9223372036854775807", "2654435760", "1000000039403724214"]
        for lit in forbidden:
            assert lit not in text, f"{m} contains suspicious literal {lit!r}"


def test_lib_rs_size_floor():
    """lib.rs stays small under the module split — just re-exports and
    pub mod declarations. A file over 3000 bytes signals someone put
    real implementation back into lib.rs instead of the per-concern
    modules; a file under 200 bytes signals the re-exports were dropped
    so main.rs and tests can't compile."""
    actual = (SRC_DIR / "lib.rs").stat().st_size
    assert 200 <= actual <= 3000, f"lib.rs is {actual} bytes (200..3000 expected)"


def test_variant_enum_declared_in_fibonacci_code_module():
    """The Variant enum lives in fibonacci_code.rs and nowhere else on
    the algorithmic surface — a decoder that inlines the enum in
    zeckendorf.rs or primes.rs violates the module boundary."""
    fc = (SRC_DIR / "fibonacci_code.rs").read_text()
    assert "enum Variant" in fc, (
        "fibonacci_code.rs is missing the Variant enum declaration"
    )
    for other in ("zeckendorf.rs", "elias_gamma.rs", "primes.rs", "fibonacci.rs"):
        text = (SRC_DIR / other).read_text()
        assert "enum Variant" not in text, (
            f"{other} declares its own Variant enum — the enum belongs in "
            f"fibonacci_code.rs per contracts §variants.md"
        )


# ────────────────────────────────────────────────────────────────
# roundtrip_witness (2026-07-08 addendum) — 4th proof plane
# ────────────────────────────────────────────────────────────────


def _decode_fib_code(bits, variant):
    """Reference decoder — invert the canonical / reverse-msb Fibonacci
    codeword back to its Zeckendorf index list per contracts
    §variants.md and §prefix_code.md."""
    if not bits:
        return []
    canonical = bits[::-1] if variant == "reverse-msb" else bits
    if not canonical.endswith("1"):
        return None
    indices = []
    for i in range(len(canonical) - 1):
        c = canonical[i]
        if c == "1":
            indices.append(i + 2)
        elif c != "0":
            return None
    if len(canonical) >= 2 and canonical[len(canonical) - 2] != "1":
        return None
    return indices


def _entry_roundtrip(entry):
    """Reference (roundtrip_ok, bit_len) per contracts/roundtrip.md."""
    if entry["variant"] == "unknown":
        return (False, 0)
    idx = _decode_fib_code(entry["fibonacci_code"], entry["variant"])
    if idx is None:
        return (False, 0)
    n_back = sum(_fibonacci(k) for k in idx)
    if n_back == entry["n"]:
        return (True, len(entry["fibonacci_code"]))
    return (False, 0)


def test_roundtrip_witness_lowercase_hex(results_json):
    """roundtrip_witness is 64 lowercase-hex characters."""
    assert "roundtrip_witness" in results_json
    v = results_json["roundtrip_witness"]
    assert re.fullmatch(r"[0-9a-f]{64}", v), v


def test_roundtrip_witness_matches_expected(results_json):
    """roundtrip_witness matches the pinned value on the shipped corpus."""
    assert results_json["roundtrip_witness"] == EXPECTED_ROUNDTRIP_WITNESS


def test_roundtrip_witness_recomputes_from_entry_fibonacci_codes(results_json):
    """roundtrip_witness = SHA-256(canonical_json(sorted
    [{bit_len, name, roundtrip_ok}])). The Python side reconstructs
    the projection by re-decoding each entry's fibonacci_code back
    to an integer using the same F(1)=1 convention as the driver and
    comparing to the entry's n field. Entries with variant == "unknown"
    force (roundtrip_ok=false, bit_len=0). See contracts/roundtrip.md."""
    projection = []
    for e in sorted(results_json["decoded"], key=lambda x: x["name"]):
        ok, bit_len = _entry_roundtrip(e)
        projection.append({"bit_len": bit_len, "name": e["name"],
                           "roundtrip_ok": ok})
    computed = hashlib.sha256(_canonical(projection).encode()).hexdigest()
    assert computed == results_json["roundtrip_witness"], (
        "roundtrip_witness does not match SHA-256 of canonical JSON over "
        "sorted per-entry {bit_len, name, roundtrip_ok} projection"
    )


def test_roundtrip_unknown_variant_records_false(results_json):
    """fx25 is the sole unknown-variant fixture in the corpus. Its
    contribution to roundtrip_witness must be (roundtrip_ok=false,
    bit_len=0) per contracts/roundtrip.md §Per-entry round-trip."""
    e = _entry(results_json, "fx25")
    assert e["variant"] == "unknown"
    ok, bit_len = _entry_roundtrip(e)
    assert ok is False and bit_len == 0


def test_roundtrip_witness_participates_in_chain_sha256(results_json):
    """chain_sha256 depends on roundtrip_witness — perturbing it changes
    the chain hash. A driver that folds the plane into results.json but
    forgets the chain-input lex position (codeword < policy < roundtrip
    < salt < variant < wythoff) fails here."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(results_json["policy_witness"].encode())
    h.update(("0" * 64).encode())  # perturb roundtrip_witness
    h.update(results_json["salt_witness"].encode())
    h.update(results_json["variant_witness"].encode())
    h.update(results_json["wythoff_witness"].encode())
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed, (
        "chain_sha256 unchanged when roundtrip_witness is nulled — the "
        "plane does not feed into the chain hash at its lex position"
    )


def test_variant_and_roundtrip_witnesses_both_load_bearing_in_chain(results_json):
    """Perturbing BOTH variant_witness and roundtrip_witness must
    still change chain_sha256 — confirms both planes are load-bearing
    and neither is silently dropped from the chain input."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(results_json["policy_witness"].encode())
    h.update(("f" * 64).encode())  # perturb roundtrip_witness
    h.update(results_json["salt_witness"].encode())
    h.update(("f" * 64).encode())  # perturb variant_witness
    h.update(results_json["wythoff_witness"].encode())
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed


def test_roundtrip_ok_and_bit_len_not_emitted_per_entry(results_json):
    """Neither `roundtrip_ok` nor `bit_len` may appear per-entry in
    results.json — the projection is internal to the driver, only the
    aggregate roundtrip_witness scalar surfaces. Prevents scope creep
    that would silently break per-entry canonical JSON SHAs."""
    for e in results_json["decoded"]:
        assert "roundtrip_ok" not in e, (
            f"{e['name']}: roundtrip_ok leaked into per-entry results"
        )
        assert "bit_len" not in e, (
            f"{e['name']}: bit_len leaked into per-entry results"
        )


def test_roundtrip_contract_ships():
    """docs/contracts/roundtrip.md exists and names the plane's inputs
    (roundtrip_ok, bit_len) plus its chain-input lex position."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "roundtrip.md"
    assert contract.is_file(), "docs/contracts/roundtrip.md missing"
    text = contract.read_text()
    for marker in ("roundtrip_witness", "roundtrip_ok", "bit_len",
                   "fibonacci_decode", "zeckendorf_sum",
                   "codeword < policy < roundtrip < salt < variant < wythoff"):
        assert marker in text, f"roundtrip.md missing '{marker}'"


def test_decomposition_contract_ships():
    """docs/contracts/decomposition.md exists and carries the greedy
    algorithm, the F_2 = 1 convention, and the anti-hardcode rule."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "decomposition.md"
    assert contract.is_file(), "docs/contracts/decomposition.md missing"
    text = contract.read_text()
    for marker in ("F_2 = 1", "fib_index_of", "top-down",
                   "zeckendorf_indices", "zeckendorf_sum",
                   "Do not hardcode"):
        assert marker in text, f"decomposition.md missing '{marker}'"


def test_canonical_contract_ships():
    """docs/contracts/canonical.md exists and carries the ascending-
    order + non-consecutive invariants plus the empty-case pinning."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "canonical.md"
    assert contract.is_file(), "docs/contracts/canonical.md missing"
    text = contract.read_text()
    for marker in ("Ascending index order", "Non-consecutive invariant",
                   "Empty case pinning", "zeckendorf_indices(0)",
                   "phi_p == 0", "phi_q == 0"):
        assert marker in text, f"canonical.md missing '{marker}'"


def test_zeckendorf_contract_now_redirect_stub():
    """The old contracts/zeckendorf.md file redirects to decomposition.md
    and canonical.md and keeps only the primality and golden-ratio
    sections. A file that still carries the full decomposition + greedy
    text means the split rollback happened."""
    text = (SRC_DIR.parent / "docs" / "contracts" / "zeckendorf.md").read_text()
    for marker in ("decomposition.md", "canonical.md", "Primality",
                   "Golden-ratio pair"):
        assert marker in text, f"zeckendorf.md missing '{marker}'"
    # A stub should NOT re-carry the full greedy walkthrough section.
    assert "Zeckendorf decomposition (top-down greedy)" not in text, (
        "zeckendorf.md still carries the full decomposition — it should "
        "redirect to decomposition.md instead of embedding the algorithm"
    )


# ────────────────────────────────────────────────────────────────
# Cross-module discipline tests (2026-07-08 addendum)
# ────────────────────────────────────────────────────────────────


def test_fibonacci_code_module_imports_zeckendorf():
    """fibonacci_code.rs MUST reference crate::zeckendorf at least once
    — the composed decoder fibonacci_decode_n chains fibonacci_decode
    into zeckendorf_sum, forcing the layered dependency edge. A
    fibonacci_code module that leaves the composition out passes the
    canonical / reverse-msb tests but loses the round-trip proof plane."""
    text = (SRC_DIR / "fibonacci_code.rs").read_text()
    assert re.search(r"use\s+crate::zeckendorf::", text) or \
           re.search(r"crate::zeckendorf::", text), (
        "fibonacci_code.rs does not reference crate::zeckendorf — the "
        "composed decoder MUST call zeckendorf_sum from the zeckendorf "
        "module per contracts §roundtrip.md"
    )


def test_zeckendorf_module_does_not_import_fibonacci_code():
    """zeckendorf.rs must NOT import from crate::fibonacci_code — the
    greedy decomposition is upstream of the codeword serialiser. A
    reverse dependency signals the monolithic re-collapse the module
    split was designed to prevent."""
    text = _strip_comments((SRC_DIR / "zeckendorf.rs").read_text())
    assert "crate::fibonacci_code" not in text, (
        "zeckendorf.rs references crate::fibonacci_code — the decomposition "
        "layer must not depend on the codeword layer per the module split"
    )


def test_elias_gamma_module_is_pure():
    """The elias_gamma module is an independent universal code — it MUST
    NOT import from zeckendorf, fibonacci_code, or primes. A dependency
    edge from elias_gamma to any of those three signals the module
    boundaries have been elided."""
    text = _strip_comments((SRC_DIR / "elias_gamma.rs").read_text())
    for forbidden in ("crate::zeckendorf", "crate::fibonacci_code",
                      "crate::primes"):
        assert forbidden not in text, (
            f"elias_gamma.rs references {forbidden} — the module must stay "
            f"independent per the 2026-07-07 module split"
        )


def test_primes_module_is_pure():
    """The primes module is an independent primality companion — it MUST
    NOT import from zeckendorf, fibonacci_code, or elias_gamma. Primality
    is orthogonal to the coding layer; a dependency signals collapse."""
    text = _strip_comments((SRC_DIR / "primes.rs").read_text())
    for forbidden in ("crate::zeckendorf", "crate::fibonacci_code",
                      "crate::elias_gamma"):
        assert forbidden not in text, (
            f"primes.rs references {forbidden} — the primality module "
            f"must stay independent per the 2026-07-07 module split"
        )


# ────────────────────────────────────────────────────────────────
# 2026-07-09 addendum — bracket module + codeword_witness plane
# ────────────────────────────────────────────────────────────────


def test_bracket_module_exists():
    """The 2026-07-09 addendum split the golden-ratio bracketing helper
    into a dedicated /app/src/src/bracket.rs module."""
    assert (SRC_DIR / "bracket.rs").is_file(), (
        "module bracket.rs missing from /app/src/src/ — the golden "
        "bracketing helper lives there per docs/contracts/bracket.md"
    )


def test_bracket_module_declared_in_lib():
    """lib.rs declares `pub mod bracket;` on the crate root surface."""
    text = _strip_comments((SRC_DIR / "lib.rs").read_text())
    assert re.search(r"\bpub\s+mod\s+bracket\s*;", text), (
        "lib.rs does not declare `pub mod bracket;`"
    )
    assert re.search(r"golden_bracket", text), (
        "lib.rs does not re-export `golden_bracket` — the crate root "
        "surface must expose it per docs/contracts/bracket.md"
    )


def test_bracket_module_imports_fibonacci():
    """bracket.rs uses `crate::fibonacci::` — the golden-ratio pair MUST
    come from the shared Fibonacci module, not an inline table."""
    text = _strip_comments((SRC_DIR / "bracket.rs").read_text())
    assert re.search(r"use\s+crate::fibonacci", text), (
        "bracket.rs does not import from `crate::fibonacci` — the "
        "Fibonacci lookups must go through the shared module"
    )


def test_bracket_module_owns_the_pair():
    """bracket.rs is the sole surface owner of `golden_bracket`; main.rs
    MUST use the crate helper rather than the inline
    `(fibonacci(max_k + 1), fibonacci(max_k))` pattern that the pre-split
    monolith carried."""
    main_text = _strip_comments((SRC_DIR / "main.rs").read_text())
    assert "golden_bracket" in main_text, (
        "main.rs does not call `golden_bracket` — the (phi_p, phi_q) "
        "pair belongs to crate::bracket per docs/contracts/bracket.md"
    )
    # A driver that still inlines the fibonacci lookups AND names
    # golden_bracket smuggles the pre-split code path back in.
    assert not re.search(
        r"\(\s*fibonacci\(\s*max_k\s*\+\s*1\s*\)\s*,\s*fibonacci\(\s*max_k\s*\)\s*\)",
        main_text,
    ), (
        "main.rs still inlines (fibonacci(max_k + 1), fibonacci(max_k)) "
        "— use crate::bracket::golden_bracket instead"
    )


def test_bracket_module_no_hardcoded_fibonacci_table():
    """No inline Fibonacci literal above F_3 = 2 lives in bracket.rs —
    every value must come from crate::fibonacci per the shared
    single-point-of-truth pin."""
    text = _strip_comments((SRC_DIR / "bracket.rs").read_text())
    # Numbers 3, 5, 8, 13, 21, 34, 55, 89, 144 are the low Fibonacci
    # tail; their presence as raw literals in bracket.rs signals a
    # local hardcode. F_2 = 1 and F_3 = 2 sneak in as arithmetic
    # placeholders so we permit them.
    for lit in ("13", "21", "34", "55", "89", "144", "233"):
        assert lit not in text, (
            f"bracket.rs contains raw Fibonacci literal {lit!r} — the "
            f"module must call crate::fibonacci::fibonacci(k) instead"
        )


def test_bracket_contract_ships():
    """docs/contracts/bracket.md exists and names the recipe + discipline."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "bracket.md"
    assert contract.is_file(), "docs/contracts/bracket.md missing"
    text = contract.read_text()
    for marker in ("golden_bracket", "phi_p", "phi_q", "crate::fibonacci",
                   "F_{max_k + 1}", "F_{max_k}"):
        assert marker in text, f"bracket.md missing '{marker}'"


def test_codeword_witness_hex_shape(results_json):
    """codeword_witness is 64 lowercase hex chars."""
    assert "codeword_witness" in results_json
    v = results_json["codeword_witness"]
    assert re.fullmatch(r"[0-9a-f]{64}", v), v


def test_codeword_witness_matches_expected(results_json):
    """codeword_witness matches the pinned value on the shipped corpus."""
    assert results_json["codeword_witness"] == EXPECTED_CODEWORD_WITNESS


def _codeword_projection_from_decoded(decoded):
    """Reference recipe for codeword_witness — see contracts/codeword.md."""
    projection = []
    for e in sorted(decoded, key=lambda x: x["name"]):
        code = e["fibonacci_code"]
        ones_count = code.count("1")
        tail_bit = code[-1:] if code else ""
        projection.append({
            "name": e["name"],
            "ones_count": ones_count,
            "tail_bit": tail_bit,
        })
    return projection


def test_codeword_witness_recomputes_from_fibonacci_codes(results_json):
    """codeword_witness = SHA-256(canonical_json(sorted per-entry
    {name, ones_count, tail_bit} projection over fibonacci_code)) per
    contracts §codeword.md."""
    projection = _codeword_projection_from_decoded(results_json["decoded"])
    computed = hashlib.sha256(_canonical(projection).encode()).hexdigest()
    assert computed == results_json["codeword_witness"], (
        "codeword_witness does not match SHA-256 of canonical JSON over "
        "the sorted per-fixture {name, ones_count, tail_bit} projection"
    )


def test_codeword_witness_participates_in_chain_sha256(results_json):
    """chain_sha256 depends on codeword_witness — perturbing it changes
    the chain hash. A driver that folds the plane into results.json but
    forgets the chain-input lex position (codeword FIRST) fails here."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(("0" * 64).encode())  # perturb codeword_witness at lex pos 0
    h.update(results_json["policy_witness"].encode())
    h.update(results_json["roundtrip_witness"].encode())
    h.update(results_json["salt_witness"].encode())
    h.update(results_json["variant_witness"].encode())
    h.update(results_json["wythoff_witness"].encode())
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed, (
        "chain_sha256 unchanged when codeword_witness is nulled — the "
        "plane does not feed into the chain hash at its lex position"
    )


def test_codeword_ones_and_tail_not_emitted_per_entry(results_json):
    """Neither `ones_count` nor `tail_bit` may appear per-entry — the
    projection is internal to the driver, only the aggregate
    codeword_witness scalar surfaces. Prevents scope creep that would
    silently break per-entry canonical JSON SHAs."""
    for e in results_json["decoded"]:
        assert "ones_count" not in e, (
            f"{e['name']}: ones_count leaked into per-entry results"
        )
        assert "tail_bit" not in e, (
            f"{e['name']}: tail_bit leaked into per-entry results"
        )


def test_codeword_witness_reflects_unknown_variant_empty_shape(results_json):
    """For every unknown-variant / bad-magic fixture, both `ones_count`
    and `tail_bit` in the codeword projection reduce to 0 / empty string
    respectively (empty fibonacci_code per contracts §rejections.md
    §VariantUnknown)."""
    projection = _codeword_projection_from_decoded(results_json["decoded"])
    zero_stems = {"fx25", "fx26"}
    seen = 0
    for rec in projection:
        if rec["name"] in zero_stems:
            assert rec["ones_count"] == 0, (
                f"{rec['name']}: expected ones_count=0 for empty codeword, "
                f"got {rec['ones_count']}"
            )
            assert rec["tail_bit"] == "", (
                f"{rec['name']}: expected empty tail_bit for empty codeword, "
                f"got {rec['tail_bit']!r}"
            )
            seen += 1
    assert seen == len(zero_stems), (
        f"expected {len(zero_stems)} zero-code fixtures, found {seen}"
    )


def test_codeword_contract_ships():
    """docs/contracts/codeword.md exists and names the plane's inputs
    plus its chain-input lex position (codeword FIRST)."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "codeword.md"
    assert contract.is_file(), "docs/contracts/codeword.md missing"
    text = contract.read_text()
    for marker in ("codeword_witness", "ones_count", "tail_bit",
                   "fibonacci_code",
                   "codeword < policy < roundtrip < salt < variant < wythoff"):
        assert marker in text, f"codeword.md missing '{marker}'"


def test_witnesses_contract_names_nine_top_level_keys():
    """docs/contracts/witnesses.md §1 states the exact nine top-level
    keys AND §chain_sha256 names all six witness planes in the correct
    lex order."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "witnesses.md"
    text = contract.read_text()
    for key in ("chain_sha256", "codeword_witness", "decoded",
                "policy_witness", "roundtrip_witness", "salt_witness",
                "variant_witness", "witness", "wythoff_witness"):
        assert key in text, f"witnesses.md missing top-level key '{key}'"
    lex_planes = ("codeword_witness", "policy_witness", "roundtrip_witness",
                  "salt_witness", "variant_witness", "wythoff_witness")
    idxs = [text.rfind(p) for p in lex_planes]
    assert all(i > 0 for i in idxs), (
        "witnesses.md does not mention all six witness planes"
    )
    assert idxs == sorted(idxs), (
        f"witnesses.md witness-plane order is not lex-sorted: {idxs}"
    )


def test_main_no_inline_phi_pair_from_fibonacci():
    """main.rs must NOT inline the (fibonacci(max_k+1), fibonacci(max_k))
    pair — it MUST call crate::bracket::golden_bracket instead. Enforces
    the 2026-07-09 module split from the driver side."""
    text = _strip_comments((SRC_DIR / "main.rs").read_text())
    assert "golden_bracket" in text, (
        "main.rs does not call golden_bracket"
    )
    assert not re.search(
        r"fibonacci\s*\(\s*max_k\s*\+\s*1\s*\)", text
    ), (
        "main.rs still calls fibonacci(max_k + 1) inline — use "
        "crate::bracket::golden_bracket instead"
    )


# ────────────────────────────────────────────────────────────────
# 2026-07-10 addendum — wythoff module + wythoff_witness plane
# ────────────────────────────────────────────────────────────────


def test_wythoff_module_exists():
    """The 2026-07-10 addendum ships a dedicated /app/src/src/wythoff.rs
    Wythoff Beatty-pair module."""
    assert (SRC_DIR / "wythoff.rs").is_file(), (
        "module wythoff.rs missing from /app/src/src/ — the Wythoff "
        "Beatty-pair helper lives there per docs/contracts/wythoff.md"
    )


def test_wythoff_module_declared_in_lib():
    """lib.rs declares `pub mod wythoff;` and re-exports `wythoff_pair`."""
    text = _strip_comments((SRC_DIR / "lib.rs").read_text())
    assert re.search(r"\bpub\s+mod\s+wythoff\s*;", text), (
        "lib.rs does not declare `pub mod wythoff;`"
    )
    assert "wythoff_pair" in text, (
        "lib.rs does not re-export wythoff_pair on the crate root surface"
    )


def test_wythoff_module_imports_fibonacci():
    """wythoff.rs uses `crate::fibonacci::` — Wythoff Beatty pairs MUST
    come from the shared Fibonacci module (Newton-style convergents are
    the reference integer route)."""
    text = _strip_comments((SRC_DIR / "wythoff.rs").read_text())
    assert re.search(r"use\s+crate::fibonacci", text), (
        "wythoff.rs does not import from `crate::fibonacci` — the "
        "reference integer implementation uses Fibonacci ratios"
    )


def test_wythoff_module_is_integer_only():
    """wythoff.rs MUST NOT contain any floating-point tokens per
    docs/contracts/wythoff.md §Integer-only requirement. Comments are
    stripped before scanning so a normal explanatory comment (e.g. one
    that spells out φ = (1 + √5)/2 in prose) does not fail the check —
    only real code is inspected."""
    text = _strip_comments((SRC_DIR / "wythoff.rs").read_text())
    for tok in ("f32", "f64", ".sqrt("):
        assert tok not in text, (
            f"wythoff.rs contains banned floating-point token {tok!r} — "
            f"the module is integer-only per docs/contracts/wythoff.md"
        )


def test_wythoff_contract_ships():
    """docs/contracts/wythoff.md exists and names the recipe + discipline."""
    contract = SRC_DIR.parent / "docs" / "contracts" / "wythoff.md"
    assert contract.is_file(), "docs/contracts/wythoff.md missing"
    text = contract.read_text()
    for marker in ("wythoff_pair", "wythoff_witness", "Beatty",
                   "crate::fibonacci", "Integer-only", "f64"):
        assert marker in text, f"wythoff.md missing '{marker}'"


def test_wythoff_witness_hex_shape(results_json):
    """wythoff_witness is 64 lowercase hex chars."""
    assert "wythoff_witness" in results_json
    v = results_json["wythoff_witness"]
    assert re.fullmatch(r"[0-9a-f]{64}", v), v


def test_wythoff_witness_matches_expected(results_json):
    """wythoff_witness matches the pinned value on the shipped corpus."""
    assert results_json["wythoff_witness"] == EXPECTED_WYTHOFF_WITNESS


def _wythoff_pair_ref(n: int) -> tuple[int, int]:
    """Python mirror of the Rust integer-only reference — uses a
    Fibonacci convergent under the same k-cap the crate ships with
    (k ≤ 91 in the loop → f_k = F_91, f_k1 = F_92 for n saturating
    u64::MAX) and masks the result to u64 so wrap-around matches the
    driver's `as u64` cast. On the shipped corpus, n ranges up to
    u64::MAX - 1, so wythoff_a for the biggest fixture wraps
    modulo 2^64 — Python + Rust must agree on the wrap."""
    if n == 0:
        return (0, 0)
    U64_MAX = (1 << 64) - 1
    two_n = n * 2 if n * 2 <= U64_MAX else U64_MAX  # saturating_mul
    a_prev, a_curr = 1, 2  # F_2, F_3
    k = 2
    while a_prev <= two_n:
        a_prev, a_curr = a_curr, a_curr + a_prev
        k += 1
        if k > 90:
            break
    f_k = a_prev
    f_k1 = a_curr
    a = ((n * f_k1) // f_k) & U64_MAX
    b = (a + n) & U64_MAX
    return (a, b)


def test_wythoff_witness_recomputes_from_entry_n(results_json):
    """wythoff_witness = SHA-256(canonical_json(sorted [{a, b, name}]))
    where (a, b) = wythoff_pair(entry.n) per contracts/wythoff.md.
    Recomputed from the per-entry n field alone — never trusts the
    driver's plane output."""
    projection = []
    for e in sorted(results_json["decoded"], key=lambda x: x["name"]):
        a, b = _wythoff_pair_ref(int(e["n"]))
        projection.append({"a": a, "b": b, "name": e["name"]})
    computed = hashlib.sha256(_canonical(projection).encode()).hexdigest()
    assert computed == results_json["wythoff_witness"], (
        "wythoff_witness does not match SHA-256 of canonical JSON over "
        "the sorted per-fixture {a, b, name} projection"
    )


def test_wythoff_witness_participates_in_chain_sha256(results_json):
    """chain_sha256 depends on wythoff_witness — perturbing it changes
    the chain hash. A driver that folds the plane into results.json but
    forgets the chain-input lex tail (wythoff LAST) fails here."""
    h = hashlib.sha256()
    for e in results_json["decoded"]:
        s = hashlib.sha256(_canonical(e).encode()).hexdigest()
        h.update(s.encode())
    h.update(results_json["codeword_witness"].encode())
    h.update(results_json["policy_witness"].encode())
    h.update(results_json["roundtrip_witness"].encode())
    h.update(results_json["salt_witness"].encode())
    h.update(results_json["variant_witness"].encode())
    h.update(("0" * 64).encode())  # perturb wythoff_witness (lex tail)
    perturbed = h.hexdigest()
    assert results_json["chain_sha256"] != perturbed, (
        "chain_sha256 unchanged when wythoff_witness is nulled — the "
        "plane does not feed into the chain hash at its lex position"
    )


def test_wythoff_a_b_not_emitted_per_entry(results_json):
    """Neither `a` nor `b` may appear per-entry — the Wythoff pair is
    internal to the wythoff_witness projection, so downstream signers
    that pinned the entry shape at the nine documented keys stay
    undisturbed."""
    for e in results_json["decoded"]:
        assert "a" not in e, f"{e['name']}: 'a' leaked into decoded entry"
        assert "b" not in e, f"{e['name']}: 'b' leaked into decoded entry"


def test_wythoff_pair_satisfies_beatty_identity(results_json):
    """For every entry with n ≥ 1, the u64-wrapped Beatty identity
    `b == (a + n) mod 2^64` (from φ² = φ + 1) must hold on the
    projection — the b field cannot be an arbitrary hash of anything
    else."""
    U64_MAX = (1 << 64) - 1
    for e in sorted(results_json["decoded"], key=lambda x: x["name"]):
        n = int(e["n"])
        a, b = _wythoff_pair_ref(n)
        if n >= 1:
            assert b == (a + n) & U64_MAX, (
                f"{e['name']}: Beatty identity violated: b={b} a={a} n={n}"
            )
        else:
            assert (a, b) == (0, 0), (
                f"{e['name']}: n=0 must yield (0, 0), got ({a}, {b})"
            )


# ─────────────────────────────────────────────────────────────────────
# §negafibonacci — signed-integer Zeckendorf variant (2026-07-11 add).
#
# The `zeckendorf-encode negafib --n <signed_int>` one-off subcommand
# backs the crate::negafibonacci module. Batch mode is unchanged; these
# tests exercise the subcommand end-to-end via the compiled binary.
# ─────────────────────────────────────────────────────────────────────

def _ref_negafib_indices(n):
    """Reference: greedy negafibonacci decomposition + Bunder collapse."""
    if n == 0:
        return []

    def fib(k):
        # crate convention: F_2 = 1, F_3 = 2, F_4 = 3, F_5 = 5, ...
        assert k >= 2
        a, b = 1, 2
        if k == 2:
            return a
        if k == 3:
            return b
        for _ in range(4, k + 1):
            a, b = b, a + b
        return b

    def negafib_abs(k):
        return 1 if k == 1 else fib(k)

    def negafib_value(k):
        v = negafib_abs(k)
        return -v if k % 2 == 0 else v

    def find_k(m):
        k = 1
        while True:
            v = negafib_value(k)
            sign = (v > 0) - (v < 0)
            msign = (m > 0) - (m < 0)
            if sign == msign and abs(v) >= abs(m):
                return k
            k += 1

    out = []
    m = n
    while m != 0:
        k = find_k(m)
        out.append(k)
        m -= negafib_value(k)

    changed = True
    while changed:
        out.sort()
        out = sorted(set(out))
        changed = False
        nx, i = [], 0
        while i < len(out):
            if i + 1 < len(out) and out[i + 1] == out[i] + 1:
                if out[i] >= 2:
                    nx.append(out[i] - 1)
                i += 2
                changed = True
            else:
                nx.append(out[i])
                i += 1
        out = nx
    return out


def _run_negafib(n):
    """Invoke `zeckendorf-encode negafib --n <n>` and return (rc, stdout, stderr)."""
    proc = subprocess.run(
        [str(BINARY), "negafib", "--n", str(n)],
        capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


@pytest.mark.parametrize("n", [0, 1, -1, 2, -2, 3, -3, 5, -5, 100, -100,
                               987, -987, 12345, -54321, 10**9, -(10**9)])
def test_negafib_subcommand_matches_reference(n):
    """`negafib --n <n>` output matches the reference decomposition for every input."""
    rc, out, err = _run_negafib(n)
    assert rc == 0, f"negafib --n {n} failed: rc={rc} err={err}"
    payload = json.loads(out)
    assert payload["n"] == n
    assert payload["reconstructed"] == n
    assert payload["is_minimal"] is True
    assert payload["indices"] == _ref_negafib_indices(n)


def test_negafib_subcommand_json_keys_lex_sorted():
    """Subcommand output keys are lex-sorted: indices < is_minimal < n < reconstructed."""
    rc, out, err = _run_negafib(42)
    assert rc == 0, err
    text = out
    keys_in_order = re.findall(r'"(indices|is_minimal|n|reconstructed)"', text)
    assert keys_in_order == ["indices", "is_minimal", "n", "reconstructed"]


def test_negafib_zero_is_empty_vector():
    """n=0 canonically decomposes to the empty index list."""
    rc, out, err = _run_negafib(0)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["indices"] == []
    assert payload["reconstructed"] == 0


def test_negafib_reconstruction_never_diverges():
    """Across a sample of 25 signed inputs, reconstructed == n and indices are canonical."""
    import random
    rng = random.Random(0xF1B0)
    for _ in range(25):
        n = rng.randint(-(10**12), 10**12)
        rc, out, err = _run_negafib(n)
        assert rc == 0, f"n={n} failed: {err}"
        payload = json.loads(out)
        idx = payload["indices"]
        assert payload["reconstructed"] == n, f"n={n}: reconstruction {payload['reconstructed']} != {n}"
        assert payload["is_minimal"] is True
        for i in range(1, len(idx)):
            assert idx[i] > idx[i - 1], f"n={n}: indices not strictly ascending {idx}"
            assert idx[i] != idx[i - 1] + 1, f"n={n}: adjacent indices {idx}"


def test_negafib_sum_overflow_rejects():
    """|n| > 1e18 hits the SumOverflow rejection with exit code 4."""
    rc, out, err = _run_negafib(10**18 + 1)
    assert rc == 4, f"expected exit 4, got {rc}"
    assert "SumOverflow" in err


def test_negafib_negative_sum_overflow_rejects():
    """|n| > 1e18 on the negative side also rejects with SumOverflow."""
    rc, out, err = _run_negafib(-(10**18 + 1))
    assert rc == 4, f"expected exit 4, got {rc}"
    assert "SumOverflow" in err


def test_negafibonacci_module_declared_in_lib():
    """lib.rs declares `pub mod negafibonacci;` — the module ships as
    part of the crate surface, not the decoy tree."""
    text = SRC_DIR.joinpath("lib.rs").read_text()
    assert re.search(r"\bpub\s+mod\s+negafibonacci\s*;", text), (
        "lib.rs is missing `pub mod negafibonacci;`"
    )


def test_negafibonacci_module_file_exists():
    """The negafibonacci module ships as its own file under src/src/."""
    assert SRC_DIR.joinpath("negafibonacci.rs").exists(), (
        "environment/src/src/negafibonacci.rs missing"
    )


def test_negafibonacci_module_no_todo_stubs():
    """No `todo!()` bodies remain in the shipped negafibonacci module."""
    text = SRC_DIR.joinpath("negafibonacci.rs").read_text()
    stripped = re.sub(r"//.*", "", text)
    stripped = re.sub(r"/\*.*?\*/", "", stripped, flags=re.DOTALL)
    assert "todo!" not in stripped, "negafibonacci.rs still has `todo!()` stub bodies"


def test_negafibonacci_module_contract_ships():
    """docs/contracts/negafibonacci.md ships with the task."""
    p = Path("/app/src/docs/contracts/negafibonacci.md")
    assert p.exists(), "docs/contracts/negafibonacci.md missing"
    text = p.read_text()
    for section in ("§values", "§recipe", "§identity", "§canonical",
                    "§reconstruct", "§subcommand", "§exit-codes"):
        assert section in text, f"negafibonacci.md missing {section} section"


# ─────────────────────────────────────────────────────────────────────
# §pisano-period — Pisano period π(m) subcommand (2026-07-15 addendum).
#
# `zeckendorf-encode pisano-period --m <u64>` computes the smallest
# positive p such that the Fibonacci sequence mod m repeats with
# period p. Pinned against OEIS A001175 reference values.
# ─────────────────────────────────────────────────────────────────────


def _ref_pisano_period(m: int) -> int:
    """Reference: smallest positive p with (F_2+p, F_3+p) == (1, 2) mod m."""
    assert m >= 1
    if m == 1:
        return 1
    a, b = 1 % m, 2 % m
    sa, sb = a, b
    p = 0
    while True:
        a, b = b, (a + b) % m
        p += 1
        if a == sa and b == sb:
            return p


def _run_pisano(m: int):
    proc = subprocess.run(
        [str(BINARY), "pisano-period", "--m", str(m)],
        capture_output=True, text=True, timeout=30,
    )
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()


# OEIS A001175 pinned values — smallest values plus a large sample.
PISANO_PINS = [
    (1, 1),   (2, 3),    (3, 8),    (4, 6),    (5, 20),
    (6, 24),  (7, 16),   (8, 12),   (9, 24),   (10, 60),
    (11, 10), (12, 24),  (13, 28),  (14, 48),  (15, 40),
    (16, 24), (17, 36),  (18, 24),  (19, 18),  (20, 60),
    (50, 300), (100, 300), (1000, 1500), (10000, 15000),
]


@pytest.mark.parametrize("m,expected", PISANO_PINS)
def test_pisano_period_matches_oeis_a001175(m, expected):
    """`pisano-period --m <m>` output matches OEIS A001175 for m in
    {1..20, 50, 100, 1000, 10000} — every value pinned verbatim."""
    rc, out, err = _run_pisano(m)
    assert rc == 0, f"pisano-period --m {m} failed: rc={rc} err={err}"
    payload = json.loads(out)
    assert payload["m"] == m
    assert payload["pisano_period"] == expected, (
        f"π({m}): got {payload['pisano_period']}, OEIS A001175 says {expected}"
    )


@pytest.mark.parametrize("m", [21, 42, 55, 77, 143, 233, 987, 1597, 4181, 65537])
def test_pisano_period_matches_python_reference(m):
    """`pisano-period --m <m>` matches Python reference recomputation."""
    rc, out, err = _run_pisano(m)
    assert rc == 0, err
    payload = json.loads(out)
    assert payload["pisano_period"] == _ref_pisano_period(m)


def test_pisano_period_stdout_keys_lex_sorted():
    """Subcommand stdout has lex-sorted keys m < pisano_period."""
    rc, out, err = _run_pisano(10)
    assert rc == 0, err
    keys = re.findall(r'"(m|pisano_period)"', out)
    assert keys == ["m", "pisano_period"]


def test_pisano_period_rejects_zero_modulus():
    """NonPositiveModulus (exit 6) fires when --m = 0."""
    rc, out, err = _run_pisano(0)
    assert rc == 6, f"expected exit 6, got {rc}"
    assert "NonPositiveModulus" in err


def test_pisano_period_rejects_overflow():
    """ModulusOverflow (exit 7) fires when --m > 1e9."""
    rc, out, err = _run_pisano(10**10)
    assert rc == 7, f"expected exit 7, got {rc}"
    assert "ModulusOverflow" in err


def test_pisano_period_boundary_m_equals_one():
    """π(1) = 1 — every Fibonacci residue is 0 mod 1, so the sequence
    repeats with period 1 from the start."""
    rc, out, err = _run_pisano(1)
    assert rc == 0, err
    assert json.loads(out)["pisano_period"] == 1


def test_pisano_period_is_deterministic():
    """Same --m across two invocations produces byte-identical output."""
    rc1, out1, _ = _run_pisano(60)
    rc2, out2, _ = _run_pisano(60)
    assert rc1 == 0 and rc2 == 0
    assert out1 == out2


def test_pisano_module_declared_in_lib():
    """lib.rs declares `pub mod pisano;` and re-exports pisano_period."""
    text = Path("/app/src/src/lib.rs").read_text()
    assert re.search(r"\bpub\s+mod\s+pisano\s*;", text), "lib.rs missing pub mod pisano"
    assert re.search(r"\bpub\s+use\s+pisano::pisano_period\b", text), (
        "lib.rs missing `pub use pisano::pisano_period;` re-export"
    )
