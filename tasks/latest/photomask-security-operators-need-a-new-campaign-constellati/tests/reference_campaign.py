"""Independent contract helpers for threatcomp verification."""

import hashlib
import json


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def digest(value):
    text = value if isinstance(value, str) else canonical(value)
    return "sha256:" + hashlib.sha256(text.encode()).hexdigest()


def without(obj, *keys):
    return {k: v for k, v in obj.items() if k not in keys}


def overlap(a0, a1, b0, b1):
    return a0 < b1 and b0 < a1


def effective(obs, policy):
    hit = any(
        e["toolcell"].strip().lower() == obs["toolcell"].strip().lower()
        and overlap(obs["start"], obs["end"], e["start"], e["end"])
        for e in policy["maintenance_epochs"]
    )
    return obs["reliability_bp"] * 3 // 5 if hit else obs["reliability_bp"]


def campaign_id(members):
    return (
        "campaign-"
        + hashlib.sha256(",".join(sorted(members)).encode()).hexdigest()[:12]
    )


def assert_canonical_bytes(raw: bytes, obj) -> None:
    assert raw == (canonical(obj) + "\n").encode("utf-8")


def validate_board(board):
    return (
        board.get("schema") == "threatcomp.evidence-board/v1"
        and "captured_policy" in board
        and board["checksum"] == digest(without(board, "checksum"))
        and board["policy_fingerprint"] == digest(board["captured_policy"])
    )


def validate_constellation(c):
    return (
        c.get("schema") == "threatcomp.campaign-constellation/v1"
        and c["checksum"] == digest(without(c, "checksum"))
        and c["payload_digest"]
        == digest(without(c, "epoch", "payload_digest", "checksum"))
    )


def validate_chronicle_line(line: str, constellation: dict) -> bool:
    if line != canonical(json.loads(line)):
        return False
    obj = json.loads(line)
    required = {
        "epoch",
        "payload_digest",
        "board_checksum",
        "campaign_count",
        "frontier_count",
    }
    if set(obj.keys()) != required:
        return False
    return (
        obj["epoch"] == constellation["epoch"]
        and obj["payload_digest"] == constellation["payload_digest"]
        and obj["board_checksum"] == constellation["board_checksum"]
        and obj["campaign_count"] == len(constellation["campaigns"])
        and obj["frontier_count"] == len(constellation["unassigned_frontier"])
    )


def validate_brief(b, constellation=None):
    if b.get("schema") != "threatcomp.campaign-brief/v1":
        return False
    if b["checksum"] != digest(without(b, "checksum")):
        return False
    for key in (
        "constellation_checksum",
        "epoch",
        "ranked_campaigns",
        "contradiction_summary",
        "unassigned_count",
    ):
        if key not in b:
            return False
    if constellation is not None:
        if b["constellation_checksum"] != constellation["checksum"]:
            return False
        if b["epoch"] != constellation["epoch"]:
            return False
        if b["unassigned_count"] != len(constellation["unassigned_frontier"]):
            return False
        expected_summary = {}
        for cut in constellation.get("contradiction_cuts", []):
            reason = cut["reason"]
            expected_summary[reason] = expected_summary.get(reason, 0) + 1
        if b["contradiction_summary"] != expected_summary:
            return False
    for item in b["ranked_campaigns"]:
        for key in (
            "rank",
            "campaign_id",
            "confidence_band",
            "confidence_bp",
            "cohesion_bp",
            "members",
        ):
            if key not in item:
                return False
    ranks = [x["rank"] for x in b["ranked_campaigns"]]
    if ranks != list(range(1, len(ranks) + 1)):
        return False
    return True
