"""Verifier for the Nix-style binary-cache closure planner."""

from __future__ import annotations

import hashlib
import itertools
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest


TASK_DIR = Path("/app/task_file")
BIN_PATH = Path("/app/bin/closure-plan")
PUBLIC_CASE = TASK_DIR / "cases" / "public"
SAMPLES_DIR = TASK_DIR / "cases" / "samples"
OUT_DIR = Path("/app/out")


PROTECTED_HASHES: dict[str, str] = {
    "CLOSURE_PLAN_CONTRACT.txt": "6fb7d881d747dc3dae72b9ce664fade08e57b932c9b0ae37d7b55fa0aba24ee6",
    "Makefile": "9420b90eea2a54aa10d81f1675c78f596452777cbce0324b9022f0501b50a1ee",
    "cases/public/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/public/local.txt": "51308ab2111e188874046a0c9b2ed9e831412c29a257266628040eeeee879872",
    "cases/public/narinfo/app-cacheA.nar": "7269b24411b58bdbecdd9949639fe295966380aa1928fd8b5970c1e7513fbc69",
    "cases/public/narinfo/app-cacheB.nar": "a054ea99b4073ed5515157a4dab0e0132c19a3b89e9d72ebd5f56283334231e0",
    "cases/public/narinfo/ca-cacheA.nar": "e5f5b6cee6b465717ae0038559b3b9e0d909f3a38cc3b82aaa4d1860162f6396",
    "cases/public/narinfo/lib-cacheA-badsig.nar": "b06e2a1d6941df899453143c6fb9be6e1f5d1668105c345bfc3eb444cc780b7e",
    "cases/public/narinfo/lib-cacheB.nar": "d104872222b182cf0ae510533749034af5a944368767111962d4b4fa5cf7edde",
    "cases/public/narinfo/lib-cacheC.nar": "64dbdcce3b3e4e8c950b0ffe47cae110dd3bcaa2bba6424853910f82ca3beb39",
    "cases/public/narinfo/ssl-cacheA.nar": "370dbc35eaeee456b0511585cbf3433c6f29fc57ef9f711147528064ba911ca9",
    "cases/public/narinfo/ssl-cacheB-held.nar": "6f95abcbb6e8d1079f634476664c14a36da075dd50e7df6dc904cc956e2f9a5e",
    "cases/public/narinfo/ssl-cacheC-badhash.nar": "640f35056fb5f255453707273f7848c196aafea02321f2da7a4ffd32997b51c4",
    "cases/public/narinfo/zlib-cacheA.nar": "ffce3004c1e14dd10153d0e1f70279843014a3e372506a919af405042701fda4",
    "cases/public/narinfo/zlib-cacheB-ref-mismatch.nar": "a5ee65ad954df64c7c982ae8c29e81329d6632b69e34a4ebb2e3c549cfeca813",
    "cases/public/objects.txt": "0f5ad5b5f71a16cde092184e3e929ac42f86edbc429246ee808f7c1da6ce84a9",
    "cases/public/policy.txt": "4dbfb6cd257772d27e36ced0c7d5053d1752d3ab790ab488e453422b7b06c3ad",
    "cases/public/roots.txt": "6303a3f8607c82dd0e30a137137516f235fc43a9f201af3bee59a24dfcece27b",
    "cases/samples/cache-rank/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/samples/cache-rank/local.txt": "c22f1879b6337d85b4fe7dcaa09cbc4210f145b12f33336c6a7186b31c72491d",
    "cases/samples/cache-rank/narinfo/widget-alpha.nar": "9bcea764de0b349b93eab302f66c743ef952b41b5387412e15444cb5efa0b784",
    "cases/samples/cache-rank/narinfo/widget-beta.nar": "67ffa491b7d678b65d9c5b91855cd596f49d537d17ed67a2e920b858487db6b8",
    "cases/samples/cache-rank/objects.txt": "c847c2a8832000ca0381d86329d5c68970354d5f02061dc9e6a6b0df04e85229",
    "cases/samples/cache-rank/policy.txt": "54acd6007ace79283bf62cc8fbf06242e719850add58ae44db1f245683f7461f",
    "cases/samples/cache-rank/roots.txt": "ddde860d70045137727c2f011ad61d8d816c47826508b0d59d97a77a9006f580",
    "cases/samples/held-cache/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/samples/held-cache/local.txt": "c22f1879b6337d85b4fe7dcaa09cbc4210f145b12f33336c6a7186b31c72491d",
    "cases/samples/held-cache/narinfo/app-fast-held.nar": "a4ac291c8b78e063af67fbe38be44e637b8a2ec6e900d9dfb1fb04fdbf2e91b4",
    "cases/samples/held-cache/narinfo/app-slow.nar": "a5f208471a8b25b961c67567c7aac78d7ba9f09dcca8842b09cac84fca391117",
    "cases/samples/held-cache/narinfo/dep-fast.nar": "e523ee7af1157c401e44b4b8c2545e107b3342d6495b45787693bf357f0f2cf5",
    "cases/samples/held-cache/objects.txt": "c0513c3542180f91a278604a35bb6996d77f59899a1ba89da2fcaf3e62a24cfa",
    "cases/samples/held-cache/policy.txt": "6fd848eea5f717d737b8c4de5625a11a8ade7345ddaabe5da46dff393feed29b",
    "cases/samples/held-cache/roots.txt": "736a6e0f75f2093ee12b45072f83fad90356c283eb37b18a28d85c48996a9d72",
    "cases/samples/nar-budget/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/samples/nar-budget/local.txt": "c22f1879b6337d85b4fe7dcaa09cbc4210f145b12f33336c6a7186b31c72491d",
    "cases/samples/nar-budget/narinfo/left.nar": "44d4b67dbfa0345356dbf2e56f50a6182d53b5c3a3fb10e3a4ab1acbd6418486",
    "cases/samples/nar-budget/narinfo/right.nar": "97cb03817ba682ebea2c914aaf559341ae9d25f7a8c0bf762565a38aa06f67ae",
    "cases/samples/nar-budget/narinfo/top.nar": "d82e6ba7e4cab2866377a6bdbac018af30047af5ede2e798d1c7fa10871cddba",
    "cases/samples/nar-budget/objects.txt": "6ec2cb89d0473c17a875c2a8b44ef2c6cfc2d17277b75351b360569e9570428e",
    "cases/samples/nar-budget/policy.txt": "c6abc27dd6f1f4b847fd1600b9e6457c4c6991102b05d7ee0b9b76d771bad4f9",
    "cases/samples/nar-budget/roots.txt": "e60ae67fb5426420ce3cb95930cc9f0c1e3dcd58b2c1cde7b783373535cff2ab",
    "cases/samples/ref-mismatch-unsat/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/samples/ref-mismatch-unsat/local.txt": "c22f1879b6337d85b4fe7dcaa09cbc4210f145b12f33336c6a7186b31c72491d",
    "cases/samples/ref-mismatch-unsat/narinfo/app-badrefs.nar": "785758cddcfae9945af2bc402c6197b86924923501d25d876a43fb25ff8cb602",
    "cases/samples/ref-mismatch-unsat/narinfo/dep-ok.nar": "8c26a40d023d20d72762fe2c3663ae605e45f1f794cea9f977d8e7b8304ecb29",
    "cases/samples/ref-mismatch-unsat/objects.txt": "2aa6ac0c1dfec27a43e865b97e8dcafd50b2e3a7dab3c4af0842b218f3e0f86c",
    "cases/samples/ref-mismatch-unsat/policy.txt": "0dee3e6bad484e4b8eca95b5bfa8127b86d0e20a6c2dfabed7e8a04e2de6be49",
    "cases/samples/ref-mismatch-unsat/roots.txt": "736a6e0f75f2093ee12b45072f83fad90356c283eb37b18a28d85c48996a9d72",
    "cases/samples/tiebreak-local-build/cache/stale-closure.json": "a7843327d9aa1f58d6f3a04a414a7ccec4256960b445fddbf9eb24427524252f",
    "cases/samples/tiebreak-local-build/local.txt": "aa4e82500ecda4565afe62e8b1b27ca2a4b74d43afd4e58f5355bedca46223bc",
    "cases/samples/tiebreak-local-build/narinfo/tool.nar": "3b4c53229710592e4bfa0526fc5643bf1807c5e93e4e8ff05e146f6fcf103da3",
    "cases/samples/tiebreak-local-build/objects.txt": "499e4585daefef47755c095dfe8b2dc1f67b2370378fc43ccdceba3b2ad7e2ac",
    "cases/samples/tiebreak-local-build/policy.txt": "69814f4d6b9aff62cea4758b7724f137701ad3c3c4d5db12ed85fdd76a87ccb3",
    "cases/samples/tiebreak-local-build/roots.txt": "96f85955aeed845efd9235fe563be2ea0de95cd68d38205d8c9a5cc70dcc636e",
    "go.mod": "685ab0dc846f0817a21b5641f624bd6bd15379e7c3c12108e34a6474b712faaf",
}

UNSAT_CLOSURE = {
    "status": "unsat",
    "roots": [],
    "actions": [],
    "summary": {
        "local": 0,
        "substituted": 0,
        "built": 0,
        "total_nar_size": 0,
        "total_build_cost": 0,
        "total_risk": 0,
        "reason": "no_plan",
    },
}
UNSAT_TSV = "store\taction\tcache\tnar_size\tbuild_cost\trisk\tdetail\nNONE\tunsat\t-\t0\t0\t0\tno_plan\n"


@dataclass(frozen=True)
class Trust:
    rank: int
    risk: int
    threshold: int
    keys: set[str]


@dataclass(frozen=True)
class Hold:
    cache: str
    store: str
    until: str
    reason: str


@dataclass(frozen=True)
class Obj:
    store: str
    system: str
    mode: str
    output_hash: str
    build_cost: int
    build_allowed: bool
    risk: int
    refs: tuple[str, ...]


@dataclass(frozen=True)
class Nar:
    store: str
    cache: str
    nar_hash: str
    nar_size: int
    sigs: set[str]
    refs: tuple[str, ...]
    deriver: str
    filename: str


@dataclass
class Case:
    system: str = ""
    now: str = ""
    limit_nar: int = 0
    limit_build: int = 0
    limit_risk: int = 0
    trust: dict[str, Trust] = field(default_factory=dict)
    holds: list[Hold] = field(default_factory=list)
    roots: list[str] = field(default_factory=list)
    local: set[str] = field(default_factory=set)
    objects: dict[str, Obj] = field(default_factory=dict)
    nars: list[Nar] = field(default_factory=list)


@dataclass(frozen=True)
class Cand:
    store: str
    kind: str
    source: str
    valid: bool
    reason: str
    risk: int
    nar_size: int
    build_cost: int
    cache: str | None
    nar_hash: str | None
    sig_count: int
    refs: tuple[str, ...]
    mode: str

    def signature(self) -> str:
        cache = self.cache if self.cache is not None else "-"
        return f"{self.store}:{self.kind}:{cache}"


def split_list(value: str) -> tuple[str, ...]:
    if value == "-":
        return ()
    return tuple(sorted(part for part in value.split(",") if part))


def useful_lines(path: Path) -> list[list[str]]:
    rows: list[list[str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line and not line.startswith("#"):
            rows.append(line.split())
    return rows


def read_case(root: Path) -> Case:
    case = Case()
    for parts in useful_lines(root / "policy.txt"):
        tag = parts[0]
        if tag == "SYSTEM":
            case.system = parts[1]
        elif tag == "NOW":
            case.now = parts[1]
        elif tag == "LIMIT_NAR":
            case.limit_nar = int(parts[1])
        elif tag == "LIMIT_BUILD":
            case.limit_build = int(parts[1])
        elif tag == "LIMIT_RISK":
            case.limit_risk = int(parts[1])
        elif tag == "TRUST":
            case.trust[parts[1]] = Trust(int(parts[2]), int(parts[3]), int(parts[4]), set(split_list(parts[5])))
        elif tag == "HOLD":
            case.holds.append(Hold(parts[1], parts[2], parts[3], parts[4]))
        else:
            raise AssertionError(f"unknown policy tag {tag}")
    for parts in useful_lines(root / "roots.txt"):
        assert parts[0] == "ROOT"
        case.roots.append(parts[1])
    for parts in useful_lines(root / "local.txt"):
        assert parts[0] == "LOCAL"
        case.local.add(parts[1])
    for parts in useful_lines(root / "objects.txt"):
        assert parts[0] == "OBJECT"
        case.objects[parts[1]] = Obj(
            store=parts[1],
            system=parts[2],
            mode=parts[3],
            output_hash=parts[4],
            build_cost=int(parts[5]),
            build_allowed=parts[6] == "yes",
            risk=int(parts[7]),
            refs=split_list(parts[8]),
        )
    for path in sorted((root / "narinfo").glob("*.nar")):
        fields: dict[str, str] = {}
        for parts in useful_lines(path):
            fields[parts[0]] = parts[1]
        case.nars.append(
            Nar(
                store=fields["STORE"],
                cache=fields["CACHE"],
                nar_hash=fields["NAR_HASH"],
                nar_size=int(fields["NAR_SIZE"]),
                sigs=set(split_list(fields["SIGS"])),
                refs=split_list(fields["REFERENCES"]),
                deriver=fields["DERIVER"],
                filename=path.name,
            )
        )
    return case


def active_hold(case: Case, cache: str, store: str) -> str | None:
    for hold in case.holds:
        if hold.cache == cache and hold.store == store and hold.until >= case.now:
            return hold.reason
    return None


def closure(case: Case) -> list[str] | None:
    seen: set[str] = set()
    stack = list(case.roots)
    while stack:
        store = stack.pop()
        if store in seen:
            continue
        obj = case.objects.get(store)
        if obj is None:
            return None
        seen.add(store)
        stack.extend(obj.refs)
    return sorted(seen)


def substitute_candidate(case: Case, obj: Obj, nar: Nar) -> Cand:
    reason = "ok"
    valid = True
    trust = case.trust.get(nar.cache)
    sig_count = 0
    if trust is None:
        valid, reason = False, "untrusted_cache"
        risk = obj.risk
    else:
        sig_count = len(nar.sigs & trust.keys)
        risk = obj.risk + trust.risk
        hold_reason = active_hold(case, nar.cache, obj.store)
        if obj.system != case.system:
            valid, reason = False, "system_mismatch"
        elif hold_reason is not None:
            valid, reason = False, f"active_hold:{hold_reason}"
        elif sig_count < trust.threshold:
            valid, reason = False, "bad_signature"
        elif tuple(sorted(nar.refs)) != obj.refs:
            valid, reason = False, "ref_mismatch"
        elif obj.mode in {"fixed", "ca"} and nar.nar_hash != obj.output_hash:
            valid, reason = False, "hash_mismatch"
    return Cand(obj.store, "substitute", nar.cache, valid, reason, risk, nar.nar_size, 0, nar.cache, nar.nar_hash, sig_count, obj.refs, obj.mode)


def candidates_for(case: Case, store: str) -> list[Cand]:
    obj = case.objects[store]
    rows: list[Cand] = []
    if store in case.local:
        rows.append(Cand(store, "local", "local", obj.system == case.system, "ok" if obj.system == case.system else "system_mismatch", 0, 0, 0, None, None, 0, obj.refs, obj.mode))
    build_valid = obj.system == case.system and obj.build_allowed and (obj.mode == "input" or obj.output_hash != "-")
    if obj.system != case.system:
        build_reason = "system_mismatch"
    elif not build_valid:
        build_reason = "build_forbidden"
    else:
        build_reason = "ok"
    rows.append(Cand(store, "build", "build", build_valid, build_reason, obj.risk, 0, obj.build_cost, None, None, 0, obj.refs, obj.mode))
    nars = sorted((nar for nar in case.nars if nar.store == store), key=lambda n: (n.cache, n.nar_hash, n.filename))
    rows.extend(substitute_candidate(case, obj, nar) for nar in nars)
    return rows


def better_key(plan: tuple[Cand, ...], case: Case) -> tuple[Any, ...]:
    built = sum(1 for c in plan if c.kind == "build")
    risk = sum(c.risk for c in plan)
    nar = sum(c.nar_size for c in plan if c.kind == "substitute")
    build = sum(c.build_cost for c in plan if c.kind == "build")
    rank = sum(case.trust[c.cache].rank for c in plan if c.kind == "substitute" and c.cache in case.trust)
    return (-built, -risk, -nar, -build, rank)


def plan_sigs(plan: tuple[Cand, ...]) -> list[str]:
    return sorted(c.signature() for c in plan)


def solve_case(root: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    case = read_case(root)
    required = closure(case)
    if required is None:
        return unsat_outputs()
    all_candidates = {store: candidates_for(case, store) for store in required}
    valid_lists = [[cand for cand in all_candidates[store] if cand.valid] for store in required]
    if any(not values for values in valid_lists):
        return unsat_outputs(required, all_candidates)

    best: tuple[Cand, ...] | None = None
    best_key: tuple[Any, ...] | None = None
    for combo in itertools.product(*valid_lists):
        total_nar = sum(c.nar_size for c in combo if c.kind == "substitute")
        total_build = sum(c.build_cost for c in combo if c.kind == "build")
        total_risk = sum(c.risk for c in combo)
        if total_nar > case.limit_nar or total_build > case.limit_build or total_risk > case.limit_risk:
            continue
        key = better_key(combo, case)
        if best_key is None or key > best_key or (key == best_key and best is not None and plan_sigs(combo) < plan_sigs(best)):
            best = combo
            best_key = key
    if best is None:
        return unsat_outputs(required, all_candidates)

    by_store = {cand.store: cand for cand in best}
    actions = []
    for store in sorted(by_store):
        cand = by_store[store]
        actions.append(
            {
                "store": store,
                "action": cand.kind,
                "cache": cand.cache,
                "nar_hash": cand.nar_hash,
                "nar_size": cand.nar_size,
                "build_cost": cand.build_cost,
                "risk": cand.risk,
                "references": list(cand.refs),
            }
        )
    closure_json = {
        "status": "ok",
        "roots": sorted(case.roots),
        "actions": actions,
        "summary": {
            "local": sum(1 for c in best if c.kind == "local"),
            "substituted": sum(1 for c in best if c.kind == "substitute"),
            "built": sum(1 for c in best if c.kind == "build"),
            "total_nar_size": sum(c.nar_size for c in best if c.kind == "substitute"),
            "total_build_cost": sum(c.build_cost for c in best if c.kind == "build"),
            "total_risk": sum(c.risk for c in best),
            "reason": None,
        },
    }
    tsv = "store\taction\tcache\tnar_size\tbuild_cost\trisk\tdetail\n"
    for store in sorted(by_store):
        cand = by_store[store]
        cache = cand.cache if cand.cache is not None else "-"
        if cand.kind == "local":
            detail = "present"
        elif cand.kind == "build":
            detail = f"mode={cand.mode}"
        else:
            detail = f"sig={cand.sig_count};refs={len(cand.refs)}"
        tsv += f"{store}\t{cand.kind}\t{cache}\t{cand.nar_size}\t{cand.build_cost}\t{cand.risk}\t{detail}\n"
    raw_closure = json.dumps(closure_json, separators=(",", ":")) + "\n"
    seal = hashlib.sha256(raw_closure.encode() + b"\n" + tsv.encode()).hexdigest()
    proof = {
        "closure": required,
        "candidates": candidate_rows(required, all_candidates),
        "selected": sorted(c.signature() for c in best),
        "seal": seal,
    }
    return closure_json, tsv, proof


def candidate_rows(required: list[str], all_candidates: dict[str, list[Cand]]) -> list[dict[str, Any]]:
    rows = []
    for store in required:
        for cand in all_candidates[store]:
            rows.append(
                {
                    "store": cand.store,
                    "source": cand.source,
                    "valid": cand.valid,
                    "reason": cand.reason,
                    "risk": cand.risk,
                    "nar_size": cand.nar_size,
                    "build_cost": cand.build_cost,
                }
            )
    return rows


def unsat_outputs(required: list[str] | None = None, all_candidates: dict[str, list[Cand]] | None = None) -> tuple[dict[str, Any], str, dict[str, Any]]:
    raw_closure = json.dumps(UNSAT_CLOSURE, separators=(",", ":")) + "\n"
    seal = hashlib.sha256(raw_closure.encode() + b"\n" + UNSAT_TSV.encode()).hexdigest()
    proof = {
        "closure": [],
        "candidates": [] if required is None or all_candidates is None else candidate_rows(required, all_candidates),
        "selected": [],
        "seal": seal,
    }
    return UNSAT_CLOSURE, UNSAT_TSV, proof


def assert_json_key_order(raw: str) -> None:
    top = json.loads(raw, object_pairs_hook=list)
    assert [k for k, _ in top] == ["status", "roots", "actions", "summary"]
    top_map = dict(top)
    for action in top_map["actions"]:
        assert [k for k, _ in action] == ["store", "action", "cache", "nar_hash", "nar_size", "build_cost", "risk", "references"]
    assert [k for k, _ in dict(top)["summary"]] == ["local", "substituted", "built", "total_nar_size", "total_build_cost", "total_risk", "reason"]


def assert_proof_key_order(raw: str) -> None:
    top = json.loads(raw, object_pairs_hook=list)
    assert [k for k, _ in top] == ["closure", "candidates", "selected", "seal"]
    for row in dict(top)["candidates"]:
        assert [k for k, _ in row] == ["store", "source", "valid", "reason", "risk", "nar_size", "build_cost"]


def run_planner(case_root: Path, out_dir: Path) -> tuple[dict[str, Any], str, dict[str, Any]]:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "stale.txt").write_text("remove me\n", encoding="utf-8")
    result = subprocess.run([str(BIN_PATH), str(case_root), str(out_dir)], cwd="/app", text=True, capture_output=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""
    assert not (out_dir / "stale.txt").exists()
    files = sorted(path.name for path in out_dir.iterdir())
    assert files == ["actions.tsv", "closure.json", "proof.json"]
    closure_raw = (out_dir / "closure.json").read_text(encoding="utf-8")
    tsv = (out_dir / "actions.tsv").read_text(encoding="utf-8")
    proof_raw = (out_dir / "proof.json").read_text(encoding="utf-8")
    assert closure_raw.endswith("\n")
    assert tsv.endswith("\n")
    assert proof_raw.endswith("\n")
    assert_json_key_order(closure_raw)
    assert_proof_key_order(proof_raw)
    return json.loads(closure_raw), tsv, json.loads(proof_raw)


def assert_case(case_root: Path, out_dir: Path) -> None:
    expected_closure, expected_tsv, expected_proof = solve_case(case_root)
    actual_closure, actual_tsv, actual_proof = run_planner(case_root, out_dir)
    assert actual_closure == expected_closure
    assert actual_tsv == expected_tsv
    assert actual_proof == expected_proof


@pytest.fixture(scope="session", autouse=True)
def build_native_binary() -> None:
    """Build the submitted CLI once for every verifier entry point."""
    subprocess.run(["make", "-C", str(TASK_DIR), "clean"], cwd="/app", check=True, timeout=60)
    subprocess.run(["make", "-C", str(TASK_DIR)], cwd="/app", check=True, timeout=120)
    assert BIN_PATH.exists()


def write_case(root: Path, files: dict[str, str]) -> Path:
    (root / "narinfo").mkdir(parents=True)
    (root / "cache").mkdir()
    for name, text in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text.strip() + "\n", encoding="utf-8")
    if "cache/stale-closure.json" not in files:
        (root / "cache" / "stale-closure.json").write_text('{"stale":true}\n', encoding="utf-8")
    return root


def generated_cases(tmp_path: Path) -> list[Path]:
    return [
        write_case(
            tmp_path / "generated-expired-hold",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 30
LIMIT_BUILD 4
LIMIT_RISK 10
TRUST hot 7 1 1 h
HOLD hot root 2026-01-01T00:00:00Z expired
""",
                "roots.txt": "ROOT root",
                "local.txt": "# none",
                "objects.txt": "OBJECT root x86_64-linux fixed hroot 4 yes 4 -",
                "narinfo/root.nar": """
STORE root
CACHE hot
NAR_HASH hroot
NAR_SIZE 6
SIGS h
REFERENCES -
DERIVER root.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-system-mismatch",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 30
LIMIT_BUILD 30
LIMIT_RISK 30
TRUST cache 1 1 1 k
""",
                "roots.txt": "ROOT foreign",
                "local.txt": "LOCAL foreign",
                "objects.txt": "OBJECT foreign aarch64-linux input - 3 yes 2 -",
                "narinfo/foreign.nar": """
STORE foreign
CACHE cache
NAR_HASH nforeign
NAR_SIZE 3
SIGS k
REFERENCES -
DERIVER foreign.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-global-risk",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 40
LIMIT_BUILD 15
LIMIT_RISK 12
TRUST risky 9 5 1 r
TRUST calm 2 0 1 c
""",
                "roots.txt": "ROOT app",
                "local.txt": "# none",
                "objects.txt": """
OBJECT app x86_64-linux input - 8 yes 3 lib
OBJECT lib x86_64-linux input - 5 yes 3 -
""",
                "narinfo/app-risky.nar": """
STORE app
CACHE risky
NAR_HASH napp
NAR_SIZE 5
SIGS r
REFERENCES lib
DERIVER app.drv
""",
                "narinfo/app-calm.nar": """
STORE app
CACHE calm
NAR_HASH napp
NAR_SIZE 7
SIGS c
REFERENCES lib
DERIVER app.drv
""",
                "narinfo/lib-risky.nar": """
STORE lib
CACHE risky
NAR_HASH nlib
NAR_SIZE 5
SIGS r
REFERENCES -
DERIVER lib.drv
""",
                "narinfo/lib-calm.nar": """
STORE lib
CACHE calm
NAR_HASH nlib
NAR_SIZE 7
SIGS c
REFERENCES -
DERIVER lib.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-distinct-sig-threshold",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 30
LIMIT_BUILD 10
LIMIT_RISK 10
TRUST strict 5 0 2 s1,s2
TRUST backup 1 1 1 b1
""",
                "roots.txt": "ROOT signed",
                "local.txt": "# none",
                "objects.txt": "OBJECT signed x86_64-linux input - 4 yes 2 -",
                "narinfo/strict-duplicate.nar": """
STORE signed
CACHE strict
NAR_HASH nsigned
NAR_SIZE 3
SIGS s1,s1
REFERENCES -
DERIVER signed.drv
""",
                "narinfo/backup.nar": """
STORE signed
CACHE backup
NAR_HASH nsigned
NAR_SIZE 4
SIGS b1
REFERENCES -
DERIVER signed.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-fixed-hash-build",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 30
LIMIT_BUILD 5
LIMIT_RISK 10
TRUST cache 10 0 1 k
""",
                "roots.txt": "ROOT fod",
                "local.txt": "# none",
                "objects.txt": "OBJECT fod x86_64-linux fixed hfod 5 yes 4 -",
                "narinfo/fod-bad.nar": """
STORE fod
CACHE cache
NAR_HASH wrong
NAR_SIZE 2
SIGS k
REFERENCES -
DERIVER fod.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-local-expands-closure",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 20
LIMIT_BUILD 20
LIMIT_RISK 20
TRUST cache 1 0 1 k
""",
                "roots.txt": "ROOT shell",
                "local.txt": "LOCAL shell",
                "objects.txt": """
OBJECT shell x86_64-linux input - 8 yes 3 core
OBJECT core x86_64-linux input - 3 yes 2 -
""",
                "narinfo/core.nar": """
STORE core
CACHE cache
NAR_HASH ncore
NAR_SIZE 5
SIGS k
REFERENCES -
DERIVER core.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-lex-signature-tie",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 10
LIMIT_BUILD 10
LIMIT_RISK 10
TRUST alpha 5 1 1 a
TRUST beta 5 1 1 b
""",
                "roots.txt": "ROOT pkg",
                "local.txt": "# none",
                "objects.txt": "OBJECT pkg x86_64-linux input - 6 yes 2 -",
                "narinfo/pkg-alpha.nar": """
STORE pkg
CACHE alpha
NAR_HASH npkg
NAR_SIZE 4
SIGS a
REFERENCES -
DERIVER pkg.drv
""",
                "narinfo/pkg-beta.nar": """
STORE pkg
CACHE beta
NAR_HASH npkg
NAR_SIZE 4
SIGS b
REFERENCES -
DERIVER pkg.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-build-cost-tie",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 9
LIMIT_BUILD 20
LIMIT_RISK 10
TRUST cache 1 0 1 k
""",
                "roots.txt": "ROOT app",
                "local.txt": "# none",
                "objects.txt": """
OBJECT app x86_64-linux input - 2 yes 1 dep
OBJECT dep x86_64-linux input - 8 yes 1 -
""",
                "narinfo/app.nar": """
STORE app
CACHE cache
NAR_HASH napp
NAR_SIZE 9
SIGS k
REFERENCES dep
DERIVER app.drv
""",
                "narinfo/dep.nar": """
STORE dep
CACHE cache
NAR_HASH ndep
NAR_SIZE 9
SIGS k
REFERENCES -
DERIVER dep.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-untrusted-cache-build",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 10
LIMIT_BUILD 4
LIMIT_RISK 10
TRUST trusted 1 0 1 t
""",
                "roots.txt": "ROOT private",
                "local.txt": "# none",
                "objects.txt": "OBJECT private x86_64-linux input - 4 yes 3 -",
                "narinfo/private-rogue.nar": """
STORE private
CACHE rogue
NAR_HASH nprivate
NAR_SIZE 1
SIGS r
REFERENCES -
DERIVER private.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-exact-active-hold",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 20
LIMIT_BUILD 8
LIMIT_RISK 10
TRUST hot 9 1 1 h
TRUST cool 2 0 1 c
HOLD hot lib 2026-09-01T00:00:00Z audit
""",
                "roots.txt": "ROOT lib",
                "local.txt": "# none",
                "objects.txt": "OBJECT lib x86_64-linux input - 8 yes 3 -",
                "narinfo/lib-hot.nar": """
STORE lib
CACHE hot
NAR_HASH nlib
NAR_SIZE 3
SIGS h
REFERENCES -
DERIVER lib.drv
""",
                "narinfo/lib-cool.nar": """
STORE lib
CACHE cool
NAR_HASH nlib
NAR_SIZE 5
SIGS c
REFERENCES -
DERIVER lib.drv
""",
            },
        ),
        write_case(
            tmp_path / "generated-build-budget-unsat",
            {
                "policy.txt": """
SYSTEM x86_64-linux
NOW 2026-07-13T00:00:00Z
LIMIT_NAR 0
LIMIT_BUILD 5
LIMIT_RISK 20
TRUST cache 1 0 1 k
""",
                "roots.txt": "ROOT top",
                "local.txt": "# none",
                "objects.txt": """
OBJECT top x86_64-linux input - 4 yes 2 dep
OBJECT dep x86_64-linux input - 4 yes 2 -
""",
            },
        ),
    ]


def test_builds_native_binary() -> None:
    """Verify the submitted Go project produces the required native binary."""
    assert BIN_PATH.exists()


def test_public_and_visible_samples(tmp_path: Path) -> None:
    """Check the public and shipped sample cases against the contract oracle."""
    assert_case(PUBLIC_CASE, OUT_DIR)
    for sample in sorted(SAMPLES_DIR.iterdir()):
        if sample.is_dir():
            assert_case(sample, tmp_path / f"out-{sample.name}")


def test_generated_compatible_cases(tmp_path: Path) -> None:
    """Check hidden-style generated cases that exercise each documented rule."""
    for case_root in generated_cases(tmp_path):
        assert_case(case_root, tmp_path / f"out-{case_root.name}")


def test_copied_root_and_deterministic_rerun(tmp_path: Path) -> None:
    """Verify copied case roots, stale output replacement, and deterministic reruns."""
    copied = tmp_path / "copied-root"
    shutil.copytree(PUBLIC_CASE, copied)
    out_one = tmp_path / "out-one"
    out_two = tmp_path / "out-two"
    assert_case(copied, out_one)
    first = {name: (out_one / name).read_bytes() for name in ["closure.json", "actions.tsv", "proof.json"]}
    assert_case(copied, out_two)
    for name, content in first.items():
        assert (out_two / name).read_bytes() == content


def test_protected_inputs_unchanged() -> None:
    """Verify the task-facing contract and fixtures were not modified at runtime."""
    if not PROTECTED_HASHES:
        return
    for relative, expected in PROTECTED_HASHES.items():
        assert hashlib.sha256((TASK_DIR / relative).read_bytes()).hexdigest() == expected
