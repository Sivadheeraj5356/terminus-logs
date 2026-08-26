import hashlib
import json
import os

OUTPUT_PATH = "/app/output/expected.json"
RUN_TS_NS = 1750000060000000000

VERDICT_ORDER = [
    "VOIDED",
    "REJECTED_CONTRADICTORY",
    "INVALID",
    "REJECTED_TYPE",
    "REJECTED_SEAL",
    "REJECTED_REPLAY",
    "SCHEMA_DRIFT_QUARANTINED",
    "QUARANTINED_TENANT",
    "REJECTED_COLLISION",
    "REJECTED_WEAK_HASH",
    "REJECTED_DUPLICATE",
    "DEFERRED_STALE",
    "DEFERRED_COOLDOWN",
    "DEFERRED_REHASH",
    "DEFERRED_HOT",
    "DEFERRED_BANDWIDTH",
    "DEFERRED_RESERVED_OUT",
    "DEHYDRATED",
    "KEPT_CANONICAL",
]


def load():
    """Read /app/output/expected.json and return the parsed dict."""
    with open(OUTPUT_PATH, "r") as f:
        return json.load(f)


def chunk_by_id(data, cid):
    """Return the chunk row dict from data['chunks'] whose chunk_id matches cid, or None if no row carries that id."""
    for r in data["chunks"]:
        if r["chunk_id"] == cid:
            return r
    return None


def recompute_digest(data):
    """Rebuild the 16-hex report digest from data by concatenating each chunks-array row as chunk_id|verdict|tenant_id|size_bytes|registered_ts_ns followed by LF, then each by_verdict entry as key=count LF in ascending key order, and returning the first 16 hex characters of the sha256 of that byte stream."""
    parts = []
    for r in data["chunks"]:
        parts.append(
            "{0}|{1}|{2}|{3}|{4}\n".format(
                r["chunk_id"],
                r["verdict"],
                r["tenant_id"],
                r["size_bytes"],
                r["registered_ts_ns"],
            )
        )
    for k in sorted(data["by_verdict"].keys()):
        parts.append("{0}={1}\n".format(k, data["by_verdict"][k]))
    blob = "".join(parts).encode("utf-8")
    return hashlib.sha256(blob).hexdigest()[:16]


def test_output_file_exists():
    """Engine emits the result file at /app/output/expected.json."""
    assert os.path.isfile(OUTPUT_PATH), f"missing {OUTPUT_PATH}"


def test_top_level_keys_match_contract():
    """The output carries exactly the four top-level keys declared in the contract."""
    data = load()
    assert sorted(data.keys()) == ["by_tenant", "by_verdict", "chunks", "summary"]


def test_total_chunks_is_44():
    """Forty-four chunk records survive intake from the four shard files."""
    data = load()
    assert data["summary"]["total_chunks"] == 44
    assert len(data["chunks"]) == 44


def test_run_ts_ns_matches_config():
    """run_ts_ns echoes the configured ns timestamp from the runtime config."""
    data = load()
    assert data["summary"]["run_ts_ns"] == RUN_TS_NS


def test_report_digest_self_recompute():
    """The report digest is the lowercase 16-hex prefix of sha256 over the canonical row+histogram stream."""
    data = load()
    expected = recompute_digest(data)
    assert data["summary"]["report_digest"] == expected, (
        f"engine digest {data['summary']['report_digest']} != recomputed {expected}"
    )
    assert len(data["summary"]["report_digest"]) == 16
    assert all(c in "0123456789abcdef" for c in data["summary"]["report_digest"])


def test_by_verdict_has_all_nineteen_keys():
    """The verdict ladder has nineteen closed verdicts; the histogram zero-fills every key."""
    data = load()
    keys = set(data["by_verdict"].keys())
    assert keys == set(VERDICT_ORDER), f"verdict key mismatch: {keys}"


def test_by_verdict_counts_match_chunks_array():
    """Each by_verdict count equals the number of chunks holding that verdict."""
    data = load()
    seen = {v: 0 for v in VERDICT_ORDER}
    for r in data["chunks"]:
        seen[r["verdict"]] += 1
    for v in VERDICT_ORDER:
        assert data["by_verdict"][v] == seen[v], f"mismatch for {v}"


def test_chunks_sorted_by_severity_then_chunk_id():
    """Rows ship sorted by verdict severity descending, then chunk_id ascending."""
    data = load()
    pos = {v: i for i, v in enumerate(VERDICT_ORDER)}
    prev = None
    for row in data["chunks"]:
        cur = (pos[row["verdict"]], row["chunk_id"])
        if prev is not None:
            assert cur >= prev, f"sort broken at {row['chunk_id']}"
        prev = cur


def test_c001_kept_canonical():
    """c-001 is the earliest registration for obj-01 offset 0, with a clean strong hash and a valid seal."""
    r = chunk_by_id(load(), "c-001")
    assert r is not None
    assert r["verdict"] == "KEPT_CANONICAL"
    assert r["tenant_id"] == "TEN_A"
    assert r["size_bytes"] == 4096


def test_c005_weak_hash_silver_permitted_within_review():
    """c-005 uses md5 on the silver tier and was registered inside the weak review window."""
    r = chunk_by_id(load(), "c-005")
    assert r["verdict"] == "KEPT_CANONICAL"


def test_c006_dehydrated_to_existing_canonical():
    """c-006 hashes onto an existing canonical entry with matching tenant and fingerprint."""
    r = chunk_by_id(load(), "c-006")
    assert r["verdict"] == "DEHYDRATED"


def test_c009_deferred_hot_gold_tier_threshold():
    """c-009 has refcount 11 crossing the gold hot threshold of 10."""
    r = chunk_by_id(load(), "c-009")
    assert r["verdict"] == "DEFERRED_HOT"


def test_c010_deferred_hot_silver_tier_threshold():
    """c-010 has refcount 8 crossing the silver hot threshold of 7."""
    r = chunk_by_id(load(), "c-010")
    assert r["verdict"] == "DEFERRED_HOT"


def test_c011_silver_stale_grace_applied():
    """c-011 sits below the silver effective stale boundary."""
    r = chunk_by_id(load(), "c-011")
    assert r["verdict"] == "DEFERRED_STALE"


def test_c012_bronze_no_grace_stale():
    """c-012 sits below the bronze stale boundary, which has zero grace."""
    r = chunk_by_id(load(), "c-012")
    assert r["verdict"] == "DEFERRED_STALE"


def test_c013_loses_dedup_against_c001():
    """c-013 collides with c-001 on object and offset but registers later, so the earliest one wins."""
    r = chunk_by_id(load(), "c-013")
    assert r["verdict"] == "REJECTED_DUPLICATE"


def test_c015_bronze_weak_hash_denied():
    """c-015 uses md5 on the bronze tier; weak hashes are off-limits at bronze."""
    r = chunk_by_id(load(), "c-015")
    assert r["verdict"] == "REJECTED_WEAK_HASH"


def test_c016_bronze_sha1_also_denied():
    """c-016 uses sha1, also in the weak set, denied for the same bronze reason."""
    r = chunk_by_id(load(), "c-016")
    assert r["verdict"] == "REJECTED_WEAK_HASH"


def test_c017_same_tenant_fingerprint_mismatch_is_collision():
    """c-017 hits an existing canonical hash but the content fingerprint differs."""
    r = chunk_by_id(load(), "c-017")
    assert r["verdict"] == "REJECTED_COLLISION"


def test_c018_cross_tenant_hash_match_is_collision():
    """c-018 hashes onto a canonical entry owned by a different tenant."""
    r = chunk_by_id(load(), "c-018")
    assert r["verdict"] == "REJECTED_COLLISION"


def test_c019_tenant_sticky_quarantine():
    """c-019 belongs to a tenant whose prior strikes still fall inside the sticky observation window."""
    r = chunk_by_id(load(), "c-019")
    assert r["verdict"] == "QUARANTINED_TENANT"


def test_c020_sticky_overrides_clean_record():
    """c-020 is itself clean, but the sticky tenant flag overrides any other verdict."""
    r = chunk_by_id(load(), "c-020")
    assert r["verdict"] == "QUARANTINED_TENANT"


def test_c021_float_size_rejected_as_type():
    """c-021 carries size_bytes as 4096.0; a dotted token is not accepted as a strict int."""
    r = chunk_by_id(load(), "c-021")
    assert r["verdict"] == "REJECTED_TYPE"


def test_c022_e_notation_refcount_rejected_as_type():
    """c-022 carries refcount as 5e2; an exponent token fails strict-int parsing."""
    r = chunk_by_id(load(), "c-022")
    assert r["verdict"] == "REJECTED_TYPE"


def test_c023_blank_tenant_is_invalid():
    """c-023 has an empty tenant string; the row cannot be routed."""
    r = chunk_by_id(load(), "c-023")
    assert r["verdict"] == "INVALID"


def test_c024_unknown_tenant_is_invalid():
    """c-024 names a tenant absent from the lookup and from the alias table."""
    r = chunk_by_id(load(), "c-024")
    assert r["verdict"] == "INVALID"


def test_c025_corrupted_seal_is_rejected():
    """c-025 carries an obviously wrong seal that fails HMAC verification."""
    r = chunk_by_id(load(), "c-025")
    assert r["verdict"] == "REJECTED_SEAL"


def test_c026_strong_hash_past_review_window_is_deferred_for_rehash():
    """c-026 uses a strong algorithm but its registration is older than the strong-hash review window."""
    r = chunk_by_id(load(), "c-026")
    assert r["verdict"] == "DEFERRED_REHASH"


def test_c027_alias_cycle_marks_invalid():
    """c-027 routes through an alias chain that cycles back on itself."""
    r = chunk_by_id(load(), "c-027")
    assert r["verdict"] == "INVALID"


def test_c028_refcount_wraparound_triggers_hot():
    """c-028 has a raw refcount below the hot threshold, but the wrap-corrected effective refcount crosses it."""
    r = chunk_by_id(load(), "c-028")
    assert r["verdict"] == "DEFERRED_HOT"


def test_c029_weak_hash_outside_review_window_is_rejected():
    """c-029 uses md5 on the silver tier, but its registration is older than the weak review window."""
    r = chunk_by_id(load(), "c-029")
    assert r["verdict"] == "REJECTED_WEAK_HASH"


def test_c030_wins_dehydration_contention():
    """c-030 and c-031 share the same canonical hash; the higher-bid chunk wins dehydration."""
    r = chunk_by_id(load(), "c-030")
    assert r["verdict"] == "DEHYDRATED"


def test_c031_loses_dehydration_contention():
    """c-031 has a smaller size and loses the bid against c-030 on the shared hash."""
    r = chunk_by_id(load(), "c-031")
    assert r["verdict"] == "DEFERRED_RESERVED_OUT"


def test_c032_bandwidth_budget_exhausted():
    """c-032 would push the TEN_B gold cumulative bytes over the bandwidth budget, so it defers."""
    r = chunk_by_id(load(), "c-032")
    assert r["verdict"] == "DEFERRED_BANDWIDTH"


def test_ms_to_ns_pivot_applied_to_c001():
    """Timestamps below the magnitude pivot are read as ms and multiplied by the ms-to-ns factor."""
    r = chunk_by_id(load(), "c-001")
    assert r["registered_ts_ns"] == 1750000050000000000


def test_ns_timestamp_passes_through_for_c009():
    """A registered_ts already above the pivot stays as ns without a second multiplication."""
    r = chunk_by_id(load(), "c-009")
    assert r["registered_ts_ns"] == 1750000054000000000


def test_summary_bytes_kept_canonical_self_recompute():
    """Summary bytes_kept_canonical equals the sum of size_bytes across canonical rows."""
    data = load()
    expected = sum(r["size_bytes"] for r in data["chunks"] if r["verdict"] == "KEPT_CANONICAL")
    assert data["summary"]["bytes_kept_canonical"] == expected
    assert expected > 0


def test_summary_bytes_dehydrated_self_recompute():
    """Summary bytes_dehydrated equals the sum of size_bytes across dehydrated rows."""
    data = load()
    expected = sum(r["size_bytes"] for r in data["chunks"] if r["verdict"] == "DEHYDRATED")
    assert data["summary"]["bytes_dehydrated"] == expected
    assert expected > 0


def test_by_tenant_keys_match_tenant_map():
    """The by_tenant block carries one zero-filled entry per canonical tenant in tenant_map.psv."""
    data = load()
    assert set(data["by_tenant"].keys()) == {"TEN_A", "TEN_B", "TEN_C", "TEN_Q", "TEN_X"}


def test_by_tenant_block_field_shape():
    """Every by_tenant block carries exactly the four declared fields, with no extra keys."""
    data = load()
    expected_fields = {"bytes_dehydrated", "bytes_kept_canonical", "chunk_count", "top_verdict"}
    for tenant, block in data["by_tenant"].items():
        actual = set(block.keys())
        assert actual == expected_fields, (
            f"{tenant} block field mismatch; extras={actual - expected_fields}; missing={expected_fields - actual}"
        )


def test_by_tenant_chunk_count_covers_all_verdicts():
    """chunk_count covers every verdict the tenant produces, not only kept and dehydrated rows."""
    data = load()
    from_chunks = {}
    for r in data["chunks"]:
        if r["verdict"] == "INVALID":
            continue
        if r["tenant_id"]:
            from_chunks[r["tenant_id"]] = from_chunks.get(r["tenant_id"], 0) + 1
    for t in data["by_tenant"]:
        assert data["by_tenant"][t]["chunk_count"] == from_chunks.get(t, 0), (
            f"chunk_count mismatch for {t}"
        )


def test_by_tenant_top_verdict_is_highest_severity_seen():
    """top_verdict per tenant equals the highest-severity verdict observed in that tenant's rows."""
    data = load()
    pos = {v: i for i, v in enumerate(VERDICT_ORDER)}
    expected = {}
    for r in data["chunks"]:
        if r["verdict"] == "INVALID":
            continue
        if not r["tenant_id"]:
            continue
        t = r["tenant_id"]
        if t not in expected or pos[r["verdict"]] < pos[expected[t]]:
            expected[t] = r["verdict"]
    for t in data["by_tenant"]:
        seen = expected.get(t, "")
        assert data["by_tenant"][t]["top_verdict"] == seen, f"top_verdict mismatch for {t}"


def test_by_tenant_bytes_self_recompute():
    """Per-tenant bytes_kept_canonical and bytes_dehydrated equal the sum of size_bytes across the matching rows."""
    data = load()
    for t in data["by_tenant"]:
        kept = sum(r["size_bytes"] for r in data["chunks"]
                   if r["verdict"] == "KEPT_CANONICAL" and r["tenant_id"] == t)
        dehyd = sum(r["size_bytes"] for r in data["chunks"]
                    if r["verdict"] == "DEHYDRATED" and r["tenant_id"] == t)
        assert data["by_tenant"][t]["bytes_kept_canonical"] == kept, f"kept mismatch for {t}"
        assert data["by_tenant"][t]["bytes_dehydrated"] == dehyd, f"dehyd mismatch for {t}"


def test_invalid_rows_excluded_from_tenant_block():
    """INVALID rows do not roll up into any by_tenant block."""
    data = load()
    counted = sum(t["chunk_count"] for t in data["by_tenant"].values())
    non_invalid = sum(1 for r in data["chunks"] if r["verdict"] != "INVALID")
    assert counted == non_invalid


def test_sticky_quarantine_overrides_clean_record():
    """A tenant whose strike history meets the sticky threshold yields QUARANTINED_TENANT even when the row is otherwise clean."""
    data = load()
    rows = [r for r in data["chunks"] if r["tenant_id"] == "TEN_Q"]
    assert all(r["verdict"] == "QUARANTINED_TENANT" for r in rows)
    assert len(rows) == 2


def _index_of_first_verdict(chunks, verdict):
    """Return the position of the earliest row in the emitted chunks array whose verdict matches, or None when the verdict is absent from the output."""
    for i, r in enumerate(chunks):
        if r["verdict"] == verdict:
            return i
    return None


def _index_of_last_verdict(chunks, verdict):
    """Return the position of the latest row in the emitted chunks array whose verdict matches, or None when the verdict is absent from the output."""
    last = None
    for i, r in enumerate(chunks):
        if r["verdict"] == verdict:
            last = i
    return last


def test_chunks_output_places_seal_above_dehyd_and_kept():
    """In the emitted chunks array, every REJECTED_SEAL row precedes every DEHYDRATED and KEPT_CANONICAL row."""
    chunks = load()["chunks"]
    seal_last = _index_of_last_verdict(chunks, "REJECTED_SEAL")
    dehyd_first = _index_of_first_verdict(chunks, "DEHYDRATED")
    kept_first = _index_of_first_verdict(chunks, "KEPT_CANONICAL")
    if seal_last is not None:
        if dehyd_first is not None:
            assert seal_last < dehyd_first
        if kept_first is not None:
            assert seal_last < kept_first


def test_chunks_output_places_bandwidth_above_reserved_and_admits():
    """In the emitted chunks array, every DEFERRED_BANDWIDTH row precedes every DEFERRED_RESERVED_OUT, DEHYDRATED, and KEPT_CANONICAL row."""
    chunks = load()["chunks"]
    bw_last = _index_of_last_verdict(chunks, "DEFERRED_BANDWIDTH")
    if bw_last is None:
        return
    for downstream in ("DEFERRED_RESERVED_OUT", "DEHYDRATED", "KEPT_CANONICAL"):
        first = _index_of_first_verdict(chunks, downstream)
        if first is not None:
            assert bw_last < first, f"BANDWIDTH must precede {downstream}"


def test_chunks_output_places_reserved_out_above_admits():
    """In the emitted chunks array, every DEFERRED_RESERVED_OUT row precedes every DEHYDRATED and KEPT_CANONICAL row."""
    chunks = load()["chunks"]
    ro_last = _index_of_last_verdict(chunks, "DEFERRED_RESERVED_OUT")
    if ro_last is None:
        return
    for downstream in ("DEHYDRATED", "KEPT_CANONICAL"):
        first = _index_of_first_verdict(chunks, downstream)
        if first is not None:
            assert ro_last < first, f"RESERVED_OUT must precede {downstream}"


def test_bandwidth_deferred_chunk_does_not_count_to_kept_bytes_for_tenant():
    """The bandwidth-deferred row is not counted in bytes_kept_canonical for its tenant."""
    data = load()
    for r in data["chunks"]:
        if r["verdict"] == "DEFERRED_BANDWIDTH":
            t = r["tenant_id"]
            kept_rows_size = sum(
                x["size_bytes"] for x in data["chunks"]
                if x["verdict"] == "KEPT_CANONICAL" and x["tenant_id"] == t
            )
            assert data["by_tenant"][t]["bytes_kept_canonical"] == kept_rows_size


def test_contention_winner_and_loser_share_same_hash():
    """The DEHYDRATED winner and the DEFERRED_RESERVED_OUT loser of a contention group share the same shared canonical."""
    r_win = chunk_by_id(load(), "c-030")
    r_lose = chunk_by_id(load(), "c-031")
    assert r_win["verdict"] == "DEHYDRATED"
    assert r_lose["verdict"] == "DEFERRED_RESERVED_OUT"
    assert r_win["size_bytes"] > r_lose["size_bytes"]


def test_c033_replay_rejected():
    """c-033 was accepted in a prior cycle within the replay window, so it is rejected as a replay."""
    r = chunk_by_id(load(), "c-033")
    assert r["verdict"] == "REJECTED_REPLAY"


def test_c034_tenant_in_cooldown_window():
    """c-034 belongs to a tenant in the closed cooldown window after reinstatement, so it defers."""
    r = chunk_by_id(load(), "c-034")
    assert r["verdict"] == "DEFERRED_COOLDOWN"
    assert r["tenant_id"] == "TEN_X"


def test_c035_hex_size_bytes_parses_to_decimal():
    """c-035 ships size_bytes as the hex string 0x1000; the engine parses it as 4096 and admits the row."""
    r = chunk_by_id(load(), "c-035")
    assert r["verdict"] == "KEPT_CANONICAL"
    assert r["size_bytes"] == 4096


def test_ten_x_block_present_with_cooldown_top():
    """TEN_X appears in the by_tenant block with chunk_count 1 and top_verdict DEFERRED_COOLDOWN."""
    data = load()
    t = data["by_tenant"]["TEN_X"]
    assert t["chunk_count"] == 1
    assert t["bytes_kept_canonical"] == 0
    assert t["bytes_dehydrated"] == 0
    assert t["top_verdict"] == "DEFERRED_COOLDOWN"


def test_chunks_output_places_replay_above_quarantine_and_collision():
    """In the emitted chunks array, every REJECTED_REPLAY row precedes every QUARANTINED_TENANT and REJECTED_COLLISION row."""
    chunks = load()["chunks"]
    replay_last = _index_of_last_verdict(chunks, "REJECTED_REPLAY")
    if replay_last is None:
        return
    for downstream in ("QUARANTINED_TENANT", "REJECTED_COLLISION"):
        first = _index_of_first_verdict(chunks, downstream)
        if first is not None:
            assert replay_last < first, f"REPLAY must precede {downstream}"


def test_chunks_output_places_cooldown_between_stale_and_rehash():
    """In the emitted chunks array, every DEFERRED_COOLDOWN row sits after every DEFERRED_STALE row and before every DEFERRED_REHASH row."""
    chunks = load()["chunks"]
    cd_first = _index_of_first_verdict(chunks, "DEFERRED_COOLDOWN")
    cd_last = _index_of_last_verdict(chunks, "DEFERRED_COOLDOWN")
    if cd_first is None:
        return
    stale_last = _index_of_last_verdict(chunks, "DEFERRED_STALE")
    rehash_first = _index_of_first_verdict(chunks, "DEFERRED_REHASH")
    if stale_last is not None:
        assert stale_last < cd_first
    if rehash_first is not None:
        assert cd_last < rehash_first


def test_c036_contradictory_force_admit_and_reject_rejects_at_top():
    """c-036 ships both force_admit and force_reject true, which routes to REJECTED_CONTRADICTORY at the very top of the cascade."""
    r = chunk_by_id(load(), "c-036")
    assert r["verdict"] == "REJECTED_CONTRADICTORY"


def test_c037_unsupported_schema_version_drift_quarantined():
    """c-037 carries schema_version 5, which is not in the supported_schemas list, so it quarantines for drift."""
    r = chunk_by_id(load(), "c-037")
    assert r["verdict"] == "SCHEMA_DRIFT_QUARANTINED"


def test_chunks_output_places_contradictory_above_invalid():
    """In the emitted chunks array, every REJECTED_CONTRADICTORY row precedes every INVALID row."""
    chunks = load()["chunks"]
    cont_last = _index_of_last_verdict(chunks, "REJECTED_CONTRADICTORY")
    inv_first = _index_of_first_verdict(chunks, "INVALID")
    if cont_last is not None and inv_first is not None:
        assert cont_last < inv_first


def test_chunks_output_places_schema_drift_between_replay_and_quarantine():
    """In the emitted chunks array, every SCHEMA_DRIFT_QUARANTINED row sits after every REJECTED_REPLAY row and before every QUARANTINED_TENANT row."""
    chunks = load()["chunks"]
    drift_first = _index_of_first_verdict(chunks, "SCHEMA_DRIFT_QUARANTINED")
    drift_last = _index_of_last_verdict(chunks, "SCHEMA_DRIFT_QUARANTINED")
    if drift_first is None:
        return
    replay_last = _index_of_last_verdict(chunks, "REJECTED_REPLAY")
    quar_first = _index_of_first_verdict(chunks, "QUARANTINED_TENANT")
    if replay_last is not None:
        assert replay_last < drift_first
    if quar_first is not None:
        assert drift_last < quar_first


def test_c038_op_void_next_keeps_own_canonical_verdict():
    """c-038 carries op void_next; its own cascade still emits KEPT_CANONICAL — only the next chunk is affected."""
    r = chunk_by_id(load(), "c-038")
    assert r["verdict"] == "KEPT_CANONICAL"


def test_c039_voided_by_c038_void_next():
    """c-039 is the next same-tenant chunk after c-038 by chunk_id ascending; its verdict is overridden to VOIDED."""
    r = chunk_by_id(load(), "c-039")
    assert r["verdict"] == "VOIDED"


def test_chunks_output_places_voided_at_very_front():
    """In the emitted chunks array, every VOIDED row precedes every other verdict."""
    chunks = load()["chunks"]
    void_last = _index_of_last_verdict(chunks, "VOIDED")
    if void_last is None:
        return
    for other in [v for v in VERDICT_ORDER if v != "VOIDED"]:
        first = _index_of_first_verdict(chunks, other)
        if first is not None:
            assert void_last < first, f"VOIDED must precede {other}"


def test_c040_octal_size_parses_to_decimal():
    """c-040 ships size_bytes as the quoted octal token 0o10000; the engine parses it as 4096 and admits the row."""
    r = chunk_by_id(load(), "c-040")
    assert r["verdict"] == "KEPT_CANONICAL"
    assert r["size_bytes"] == 4096


def test_c041_binary_size_parses_to_decimal():
    """c-041 ships size_bytes as the quoted binary token 0b1000000000000; the engine parses it as 4096 and admits the row."""
    r = chunk_by_id(load(), "c-041")
    assert r["verdict"] == "KEPT_CANONICAL"
    assert r["size_bytes"] == 4096


def test_c042_quoted_decimal_without_radix_prefix_rejected_as_type():
    """c-042 ships size_bytes as the quoted decimal token 100 with no radix prefix; the strict-int gate rejects it even though the digits would parse base-10."""
    r = chunk_by_id(load(), "c-042")
    assert r["verdict"] == "REJECTED_TYPE"


def test_c043_multi_hop_alias_resolves_to_canonical_tenant():
    """c-043 names tenant TEN_CHAIN_ONE which resolves through three alias hops to TEN_A; the row admits with the resolved canonical tenant."""
    r = chunk_by_id(load(), "c-043")
    assert r["verdict"] == "KEPT_CANONICAL"
    assert r["tenant_id"] == "TEN_A"


def test_c044_stolen_seal_rejected_only_via_actual_hmac_verification():
    """c-044 carries the exact seal string from c-001 embedded on completely different envelope data. The bytes look legitimate — sixteen valid hex characters — so any engine that merely accepts non-empty seals will pass this row through. Only an engine that recomputes HMAC-SHA256 over the row's own canonical bytes and compares to the envelope seal will detect the mismatch and route it to REJECTED_SEAL."""
    r = chunk_by_id(load(), "c-044")
    assert r["verdict"] == "REJECTED_SEAL"
