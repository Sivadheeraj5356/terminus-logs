"""Protected fixture integrity checks."""

from __future__ import annotations

import hashlib
from pathlib import Path

APP = Path("/app")

PROTECTED_SHA256 = {
    "data/manifest.json": "26b117ab6b953cd53ef913e82db709d82559590d9336718572b902d212ce1ce4",
    "data/module_lock.json": "e04be6043ecb89a2bb1a4b36ccba671d1d52cd8d9af1e3900f7afc1c2fc117a5",
    "data/proxy_snapshot_jan2025.json": "f58b3239f6ccde58c8c1d4aed2ff45529cacbac77308427a5d9f11ab321da356",
    "data/conflict_report.json": "3d7ab7f300ffa2c6b226f378c987a9cf26c092bfdbe17f1581ee6d2b366d46ab",
    "data/exclude_overlay.json": "ac080d0cfaa765ee7f8d466f4fdad6b65f7240830af46c856d1d80870dfc3bdf",
    "docs/output-contract.md": "b3d88292bb37bb624c0fffc6a1c5921525282bf463774e0fa3918a762e168096",
    "corpus/policy_pack/01_refresh.txt": "2081786a3bda3396f513357dc2d9c239799b3855325731e0ca3d787a353f8575",
    "corpus/policy_pack/02_retract_sum.txt": "2262253f967ffaba3469d89159ce433dc01056b78264696b6b5c4af026fe3a44",
    "corpus/policy_pack/03_exclude_floor.txt": "5167e8162dea18fd017c8e9b111826b54fbe5b9f4ebad42bb182cf36b5356b96",
    "corpus/policy_pack/04_gate_track.txt": "3d067cb3dc135d2f1d9fea860656bc3f1ee02595d4431c500bded61350be24df",
    "corpus/policy_pack/05_waivers.txt": "c8da9b383a70310600d82a207f5c93589b6b6f0a7570b58146ea3461036bce4b",
    "corpus/policy_pack/06_counters_digests.txt": "3f786c44c03e65545661379cb2544e9130c0808d11db8018ddc0c96cf56a8e6e",
    "corpus/policy_pack/99_distractor_vendor.txt": "2cebf507b9b3efcaa41c01b99719ac55f68db181acde2b0f10178bc444a358f1",
}


def assert_protected_integrity() -> None:
    for rel, expected in PROTECTED_SHA256.items():
        path = APP / rel
        assert path.exists(), f"missing protected file {rel}"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest == expected, f"protected file modified: {rel}"
