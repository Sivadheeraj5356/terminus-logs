"""JSON-path diagnostics for Test 23 (identity-aware report arrays)."""

from __future__ import annotations

from typing import Any


def _type_name(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "boolean"
    if isinstance(v, int) and not isinstance(v, bool):
        return "integer"
    if isinstance(v, float):
        return "number"
    if isinstance(v, str):
        return "string"
    if isinstance(v, list):
        return "array"
    if isinstance(v, dict):
        return "object"
    return type(v).__name__


ROW_IDENTITY_KEYS: dict[str, tuple[str, ...]] = {
    "request_rows": ("request_id",),
    "quote_rows": ("request_id",),
    "event_rows": ("request_id", "event_log_id", "event_seq"),
    "pcr_rows": ("request_id", "pcr_index"),
    "reference_match_rows": ("request_id", "policy_id", "rule_id"),
    "counter_rows": ("request_id",),
    "nonce_rows": ("nonce_id",),
    "conflict_rows": ("request_id", "conflict_type", "subject", "reason_code"),
}


def _row_identity(row: dict[str, Any], keys: tuple[str, ...]) -> tuple[Any, ...]:
    return tuple(row.get(k) for k in keys)


def _format_identity(identity: tuple[Any, ...], keys: tuple[str, ...]) -> str:
    return ",".join(f"{k}={v!r}" for k, v in zip(keys, identity, strict=True))


def diff_reports(expected: Any, actual: Any, path: str = "$", limit: int = 8) -> list[dict]:
    diffs: list[dict] = []

    def add(**kwargs: Any) -> None:
        if len(diffs) < limit:
            diffs.append(kwargs)

    def walk_scalarish(e: Any, a: Any, p: str) -> None:
        if len(diffs) >= limit:
            return
        if type(e) is not type(a) and not (
            isinstance(e, (int, float))
            and isinstance(a, (int, float))
            and not isinstance(e, bool)
            and not isinstance(a, bool)
        ):
            add(
                path=p,
                expected_type=_type_name(e),
                actual_type=_type_name(a),
                expected_value=e if not isinstance(e, (dict, list)) else None,
                actual_value=a if not isinstance(a, (dict, list)) else None,
                missing_keys=[],
                extra_keys=[],
                array_length_difference=None,
            )
            return
        if isinstance(e, dict):
            assert isinstance(a, dict)
            ek, ak = set(e), set(a)
            missing = sorted(ek - ak)
            extra = sorted(ak - ek)
            if missing or extra:
                add(
                    path=p,
                    expected_type="object",
                    actual_type="object",
                    expected_value=None,
                    actual_value=None,
                    missing_keys=missing,
                    extra_keys=extra,
                    array_length_difference=None,
                )
            for k in sorted(ek & ak):
                walk(e[k], a[k], f"{p}.{k}", array_name=None)
        elif isinstance(e, list):
            assert isinstance(a, list)
            if len(e) != len(a):
                add(
                    path=p,
                    expected_type="array",
                    actual_type="array",
                    expected_value=None,
                    actual_value=None,
                    missing_keys=[],
                    extra_keys=[],
                    array_length_difference=len(a) - len(e),
                )
            for i, (ev, av) in enumerate(zip(e, a, strict=False)):
                walk(ev, av, f"{p}[{i}]", array_name=None)
        else:
            if e != a:
                add(
                    path=p,
                    expected_type=_type_name(e),
                    actual_type=_type_name(a),
                    expected_value=e,
                    actual_value=a,
                    missing_keys=[],
                    extra_keys=[],
                    array_length_difference=None,
                )

    def walk_identity_rows(
        e_rows: list[Any],
        a_rows: list[Any],
        p: str,
        keys: tuple[str, ...],
    ) -> None:
        if len(diffs) >= limit:
            return
        if not isinstance(e_rows, list) or not isinstance(a_rows, list):
            walk_scalarish(e_rows, a_rows, p)
            return
        if not all(isinstance(r, dict) for r in e_rows + a_rows):
            walk_scalarish(e_rows, a_rows, p)
            return

        e_ids = [_row_identity(r, keys) for r in e_rows]
        a_ids = [_row_identity(r, keys) for r in a_rows]

        # Duplicate identities
        for label, ids in (("expected", e_ids), ("actual", a_ids)):
            seen: dict[tuple[Any, ...], int] = {}
            for idx, ident in enumerate(ids):
                if ident in seen:
                    add(
                        path=f"{p}[{idx}]",
                        expected_type="row_identity",
                        actual_type="duplicate_row_identity",
                        expected_value=_format_identity(ident, keys),
                        actual_value=f"duplicate_in_{label}_at_indexes={seen[ident]},{idx}",
                        missing_keys=[],
                        extra_keys=[],
                        array_length_difference=None,
                    )
                    if len(diffs) >= limit:
                        return
                else:
                    seen[ident] = idx

        # Ordering mismatch: first index where ordered identity sequences differ
        for i, (eid, aid) in enumerate(zip(e_ids, a_ids, strict=False)):
            if eid != aid:
                add(
                    path=f"{p}[{i}]",
                    expected_type="row_identity",
                    actual_type="row_identity",
                    expected_value=_format_identity(eid, keys),
                    actual_value=_format_identity(aid, keys),
                    missing_keys=[],
                    extra_keys=[],
                    array_length_difference=None,
                    expected_index=i,
                    actual_index=i,
                    note="ordered_identity_mismatch",
                )
                break

        e_set = set(e_ids)
        a_set = set(a_ids)
        missing = sorted(e_set - a_set)
        extra = sorted(a_set - e_set)
        for ident in missing:
            payload = {
                "path": p,
                "expected_type": "row_identity",
                "actual_type": "missing_row",
                "expected_value": _format_identity(ident, keys),
                "actual_value": None,
                "missing_keys": [],
                "extra_keys": [],
                "array_length_difference": None,
            }
            if keys == ROW_IDENTITY_KEYS["conflict_rows"]:
                payload.update(
                    {
                        "request_id": ident[0],
                        "conflict_type": ident[1],
                        "subject": ident[2],
                        "reason_code": ident[3],
                    }
                )
            add(**payload)
            if len(diffs) >= limit:
                return
        for ident in extra:
            payload = {
                "path": p,
                "expected_type": "row_identity",
                "actual_type": "extra_row",
                "expected_value": None,
                "actual_value": _format_identity(ident, keys),
                "missing_keys": [],
                "extra_keys": [],
                "array_length_difference": None,
            }
            if keys == ROW_IDENTITY_KEYS["conflict_rows"]:
                payload.update(
                    {
                        "request_id": ident[0],
                        "conflict_type": ident[1],
                        "subject": ident[2],
                        "reason_code": ident[3],
                    }
                )
            add(**payload)
            if len(diffs) >= limit:
                return

        # Align common rows by identity and compare fields
        e_by = {ident: row for ident, row in zip(e_ids, e_rows, strict=True)}
        a_by = {ident: row for ident, row in zip(a_ids, a_rows, strict=True)}
        for ident in sorted(e_set & a_set):
            walk_scalarish(e_by[ident], a_by[ident], f"{p}{{{_format_identity(ident, keys)}}}")
            if len(diffs) >= limit:
                return

    def walk(e: Any, a: Any, p: str, array_name: str | None) -> None:
        if len(diffs) >= limit:
            return
        if array_name in ROW_IDENTITY_KEYS and isinstance(e, list) and isinstance(a, list):
            walk_identity_rows(e, a, p, ROW_IDENTITY_KEYS[array_name])
            return
        if isinstance(e, dict) and isinstance(a, dict) and p == "$":
            ek, ak = set(e), set(a)
            missing = sorted(ek - ak)
            extra = sorted(ak - ek)
            if missing or extra:
                add(
                    path=p,
                    expected_type="object",
                    actual_type="object",
                    expected_value=None,
                    actual_value=None,
                    missing_keys=missing,
                    extra_keys=extra,
                    array_length_difference=None,
                )
            for k in sorted(ek & ak):
                child = f"{p}.{k}" if p != "$" else f"$.{k}"
                # For top-level report arrays, pass the array name.
                walk(e[k], a[k], child, array_name=k if k in ROW_IDENTITY_KEYS else None)
            return
        walk_scalarish(e, a, p)

    walk(expected, actual, path, array_name=None)
    return diffs
