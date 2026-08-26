"""Verifier for staging_manifest, phase_journal, and loader_trace."""

import json
import subprocess
from pathlib import Path

APP = Path("/app")
ENV = APP / "environment"
OUT = APP / "output"
MANIFEST = OUT / "staging_manifest.json"
JOURNAL = OUT / "phase_journal.json"
TRACE = OUT / "loader_trace.json"
STAGING_WAVE = APP / ".staging" / "active_wave.json"
PROFILES = json.loads((ENV / "data/profiles.json").read_text())
EXEC = "/app/environment/driver/exec_w0.sh"
VALID_LANES = {"B", "O"}


def _run_cold(merge: bool = False, merge_tier: int = 0) -> None:
    if merge_tier == 2:
        subprocess.run(
            [
                "bash",
                "/app/environment/driver/exec_w0.sh",
                "--profile",
                "cold",
                "--merge-tier",
                "2",
            ],
            check=True,
        )
    elif merge:
        subprocess.run(
            ["bash", "/app/environment/driver/exec_w0.sh", "--profile", "cold", "--merge"],
            check=True,
        )
    else:
        subprocess.run(
            ["bash", "/app/environment/driver/exec_w0.sh", "--profile", "cold"],
            check=True,
        )


def _run_warm() -> None:
    subprocess.run(
        ["bash", "/app/environment/driver/exec_w0.sh", "--profile", "warm"],
        check=True,
    )


def _rebuild(profile: str, merge: bool = False, merge_tier: int = 0) -> None:
    _clear_outputs()
    if profile == "cold":
        _run_cold(merge=merge, merge_tier=merge_tier)
    else:
        _run_warm()


def _clear_outputs() -> None:
    for path in (MANIFEST, JOURNAL, TRACE):
        if path.is_file():
            path.unlink()


def _load_manifest() -> dict:
    with open(MANIFEST, encoding="utf-8") as handle:
        return json.load(handle)


def _load_journal() -> dict:
    with open(JOURNAL, encoding="utf-8") as handle:
        return json.load(handle)


def _load_trace() -> dict:
    with open(TRACE, encoding="utf-8") as handle:
        return json.load(handle)


def _load_json(path: Path) -> dict:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def _weights(profile: str) -> dict[str, int]:
    rel = PROFILES["profiles"][profile]["weights"]
    weights: dict[str, int] = {}
    with open(ENV / rel, encoding="utf-8") as handle:
        for line in handle:
            parts = line.strip().split("\t")
            if len(parts) == 2:
                weights[parts[0]] = int(parts[1])
    return weights


def _weight_order(profile: str, names: list[str]) -> list[str]:
    weights = _weights(profile)
    return sorted(names, key=lambda n: (-weights[n], n))


def _expected_stamp(profile: str, names: list[str], carry: str) -> str:
    proc = subprocess.run(
        [
            "python3",
            "-c",
            (
                "import hashlib, sys; profile, carry, *names = sys.argv[1:]; "
                "body = profile + ':' + ';'.join(sorted(names)) + ':' + carry; "
                "print(hashlib.sha256(body.encode()).hexdigest()[:16])"
            ),
            profile,
            carry,
            *names,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def _parity(profile: str) -> dict:
    required = set(PROFILES["profiles"][profile]["required"])
    manifest = _load_manifest()
    hook_state_path = APP / ".staging" / "hook_state.json"
    commits: dict[str, bool] = {}
    if hook_state_path.is_file():
        hook = _load_json(hook_state_path)
        for row in hook.get("commits", []):
            if row.get("committed"):
                commits[row["lane"]] = True
    journal_union = _journal_object_names(_load_journal())
    weights = _weights(profile)
    read_order = sorted(weights.keys(), key=lambda n: (-weights[n], n))
    manifest_names = {o["name"] for o in manifest["objects"]}
    rows = []
    for name in read_order:
        lane = next((o["lane"] for o in manifest["objects"] if o["name"] == name), "O")
        if name not in manifest_names:
            metric = 0
        elif name not in journal_union:
            metric = 0
        elif name in required and commits.get(lane, False):
            metric = 1
        elif name in required and lane == "O" and commits.get("B", False):
            metric = 1
        else:
            metric = 0
        rows.append({"object": name, "avail_metric": metric, "lane": lane})
    return {"read_order": read_order, "rows": rows}


def _index_bind_check(profile: str) -> None:
    weights = _weights(profile)
    wave = _load_json(STAGING_WAVE)
    names = sorted(o["name"] for o in wave.get("objects", []))
    expected = sorted(names, key=lambda n: (-weights[n], n))
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    chroot = _load_json(APP / ".staging" / "chroot_index.json")["order"]
    assert host == expected
    assert chroot == expected


def _row_matches_schema(row: dict) -> bool:
    if set(row.keys()) != {"object", "avail_metric", "lane"}:
        return False
    if row["avail_metric"] not in (0, 1):
        return False
    if row["lane"] not in VALID_LANES:
        return False
    return True


def _derived_status(profile: str, rows: list[dict]) -> str:
    required = PROFILES["profiles"][profile]["required"]
    metrics = {row["object"]: row["avail_metric"] for row in rows}
    if all(metrics.get(name, 0) == 1 for name in required):
        return "CLEAN"
    return "DIRTY"


def _journal_object_names(journal: dict) -> set[str]:
    names: set[str] = set()
    for seg in journal.get("segments", []):
        names.update(seg.get("objects", []))
    return names


def _active_wave_names() -> set[str]:
    wave = _load_json(STAGING_WAVE)
    return {o["name"] for o in wave.get("objects", [])}


def test_aux_k1_m1_knot() -> None:
    """Cold read_order must follow profile weight-table ordering.

    Fails when loader_trace.json sorts lexicographically instead of by descending profile weight then ascending name.
    """
    _rebuild("cold")
    trace = _load_trace()
    expected = _weight_order("cold", list(_weights("cold").keys()))
    assert trace["read_order"] == expected


def test_aux_k2_m2_bind() -> None:
    """Host and chroot index views must match weight-table order.

    Fails when host_index.json and chroot_index.json disagree or diverge from active-wave weight ordering.
    """
    _rebuild("cold")
    _index_bind_check("cold")


def test_aux_k3_m3_trap() -> None:
    """Incremental merge must adopt delta carry token and stamp.

    Fails when merge keeps WAVE_A carry or stamps parent-only names instead of the merged snapshot with WAVE_B.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    assert manifest["carry"] == "WAVE_B"
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_B")


def test_aux_k4_m2_flip() -> None:
    """Hook commits require blob_epoch equal to hook_gen.

    Any committed hook_state row with mismatched blob_epoch and hook_gen indicates the hook gate is too permissive.
    """
    _rebuild("cold")
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    journal = _load_journal()
    for seg, commit in zip(journal["segments"], hook["commits"]):
        if commit["committed"]:
            assert seg["blob_epoch"] == seg["hook_gen"]


def test_aux_k5_m5_gen() -> None:
    """Phase journal lists blob segment before object segment.

    Fails when journal emission orders O-lane staging ahead of B-lane staging.
    """
    _rebuild("cold")
    segments = _load_journal()["segments"]
    pos_b = next(i for i, seg in enumerate(segments) if seg["lane"] == "B")
    pos_o = next(i for i, seg in enumerate(segments) if seg["lane"] == "O")
    assert pos_b < pos_o


def test_aux_k6_m4_q7() -> None:
    """CLEAN status_token requires all required avail_metric values set.

    A CLEAN token with any cold-profile required object at avail_metric 0 is a false-green loader report.
    """
    _rebuild("cold")
    trace = _load_trace()
    required = PROFILES["profiles"]["cold"]["required"]
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if trace["status_token"] == "CLEAN":
        assert all(metrics.get(name, 0) == 1 for name in required)


def test_aux_k7_m1_only() -> None:
    """Loader trace avail metrics must honor hook_state gating, not manifest alone.

    Fails when the loader trace marks warm objects available without honoring hook_state lane commits.
    """
    _rebuild("warm")
    trace = _load_trace()
    parity = _parity("warm")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    for row in trace["rows"]:
        if row["object"] in PROFILES["profiles"]["warm"]["required"]:
            assert row["avail_metric"] == parity_by_object[row["object"]]["avail_metric"]


def test_aux_k8_m4_stable() -> None:
    """Second cold rebuild converges to identical read_order.

    Fails when a repeat cold driver run reshuffles read_order instead of reproducing weight-table ordering.
    """
    _clear_outputs()
    _run_cold()
    first = _load_trace()["read_order"]
    _run_cold()
    second = _load_trace()["read_order"]
    assert first == second


def test_aux_k9_m3_merge() -> None:
    """Incremental merge journal must cover every active wave object.

    Fails when phase_journal segments omit objects present in active_wave.json after merge.
    """
    _rebuild("cold", merge=True)
    journal = _load_journal()
    staged = _journal_object_names(journal)
    assert staged == _active_wave_names()


def test_aux_k10_m1_order() -> None:
    """Cold read_order weight sort survives incremental merge rebuild.

    Fails when merge rebuild falls back to name or manifest order despite an expanded cold weight table.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    expected = _weight_order("cold", list(_weights("cold").keys()))
    assert trace["read_order"] == expected


def test_aux_k11_m2_rank() -> None:
    """Warm read_order must follow profile weight-table ordering.

    Fails when warm loader_trace.json ignores the profile weight table descending-weight tie-break.
    """
    _rebuild("warm")
    trace = _load_trace()
    expected = _weight_order("warm", list(_weights("warm").keys()))
    assert trace["read_order"] == expected


def test_aux_k12_m2_epoch() -> None:
    """Blob epoch must increment when blob lane finishes staging.

    Fails when B-lane segments record blob_epoch 0 or never advance past the initial counter.
    """
    _rebuild("cold")
    segments = _load_journal()["segments"]
    blob_segments = [seg for seg in segments if seg["lane"] == "B"]
    assert blob_segments
    assert max(seg["blob_epoch"] for seg in blob_segments) >= 1


def test_aux_k13_m4_avail() -> None:
    """Cold loader avail metrics must follow hook_state gating rules.

    Fails when cold trace rows disagree with hook-gated availability on any required object.
    """
    _rebuild("cold")
    trace = _load_trace()
    parity = _parity("cold")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    for row in trace["rows"]:
        if row["object"] in PROFILES["profiles"]["cold"]["required"]:
            assert row["avail_metric"] == parity_by_object[row["object"]]["avail_metric"]


def test_aux_k14_m5_prof() -> None:
    """Staging manifest profile must match the CLI profile label.

    Fails when staging_manifest.json profile field drifts from the --profile argument.
    """
    _rebuild("warm")
    assert _load_manifest()["profile"] == "warm"
    _rebuild("cold")
    assert _load_manifest()["profile"] == "cold"


def test_aux_k15_m6_rows() -> None:
    """Loader trace rows must satisfy trace_row.schema.json.

    Fails when any row omits required keys or uses avail_metric outside {0,1} or lane outside {B,O}.
    """
    _rebuild("cold")
    for row in _load_trace()["rows"]:
        assert _row_matches_schema(row)


def test_aux_k16_m7_status() -> None:
    """Loader status_token must reflect required-object avail aggregation.

    Fails when status_token is CLEAN with a required object at 0, or DIRTY when all required objects are available.
    """
    _rebuild("cold")
    trace = _load_trace()
    assert trace["status_token"] == _derived_status("cold", trace["rows"])


def test_aux_k17_m3_disk() -> None:
    """Incremental merge must include delta wave objects in staging manifest.

    Fails when wave_b-only objects such as mod_disk are missing from staging_manifest after --merge.
    """
    _rebuild("cold", merge=True)
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_disk" in manifest_names


def test_aux_k18_m2_hooklen() -> None:
    """Hook commits array length must match phase journal segment count.

    Fails when hook_state.json commits rows are missing or extra relative to journal segments.
    """
    _rebuild("cold")
    journal = _load_journal()
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    assert len(hook["commits"]) == len(journal["segments"])


def test_aux_k19_m1_k0_base() -> None:
    """Non-merge cold run must keep parent carry token WAVE_A.

    Fails when a plain cold rebuild adopts the delta carry token without --merge.
    """
    _rebuild("cold")
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k20_m2_bind_prof() -> None:
    """Warm host and chroot index views must match weight-table order.

    Fails when warm host/chroot index files disagree on active-wave weight ordering.
    """
    _rebuild("warm")
    _index_bind_check("warm")


def test_aux_k21_m3_hook_block() -> None:
    """Object-lane segment stays uncommitted until hook_gen matches blob_epoch.

    Fails when cold non-merge runs commit the O-lane hook or set hook_gen equal to blob_epoch on O.
    """
    _rebuild("cold")
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    journal = _load_journal()
    o_commit = next(
        commit for commit, seg in zip(hook["commits"], journal["segments"]) if seg["lane"] == "O"
    )
    o_seg = next(seg for seg in journal["segments"] if seg["lane"] == "O")
    assert o_commit["committed"] is False
    assert o_seg["blob_epoch"] != o_seg["hook_gen"]


def test_aux_k22_m4_rowcount() -> None:
    """Loader trace must emit one row per weight-table object.

    Fails when trace rows are sparse relative to the profile weight TSV object list.
    """
    _rebuild("cold")
    trace = _load_trace()
    assert len(trace["rows"]) == len(_weights("cold"))


def test_aux_k23_m5_seal_prof() -> None:
    """Warm manifest stamp must match the documented digest for the active wave.

    Fails when the manifest stamp digest over profile, sorted names, and carry disagrees with staging_manifest stamp.
    """
    _rebuild("warm")
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("warm", names, manifest["carry"])


def test_aux_k24_m6_disk_avail() -> None:
    """Merged delta object mod_disk must have avail_metric 1 on cold profile.

    Fails when mod_disk is staged but still reports unavailable after a successful merge rebuild.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    assert metrics.get("mod_disk") == 1


def test_aux_k25_m7_hook_gen() -> None:
    """Segment hook_gen values must strictly increase along the journal.

    Fails when hook_gen is copied from blob_epoch or reused across segments, producing duplicates.
    """
    _rebuild("cold", merge=True)
    gens = [seg["hook_gen"] for seg in _load_journal()["segments"]]
    assert gens == sorted(gens)
    assert len(gens) == len(set(gens))


def test_aux_k26_m1_chroot_host() -> None:
    """Host and chroot index order lists must be identical after merge.

    Fails when merge rebuild writes different order arrays to host_index and chroot_index.
    """
    _rebuild("cold", merge=True)
    host = _load_json(Path("/app/.staging/host_index.json"))["order"]
    chroot = _load_json(Path("/app/.staging/chroot_index.json"))["order"]
    assert host == chroot


def test_aux_k27_m2_prof_clean() -> None:
    """Warm loader status_token must be CLEAN when required objects are available.

    Fails when a corrected warm rebuild still reports DIRTY despite all required objects at avail_metric 1.
    """
    _rebuild("warm")
    trace = _load_trace()
    assert trace["status_token"] == "CLEAN"


def test_aux_k28_m3_merge_seal() -> None:
    """Incremental merge stamp must bind sorted merged object names with WAVE_B carry.

    Fails when merge stamp is computed from parent-only names or the wrong carry token.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_B")


def test_aux_k29_m4_absent() -> None:
    """Cold non-merge must report mod_disk unavailable.

    Fails when trace marks weight-table objects available without staging them in the manifest.
    """
    _rebuild("cold")
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    assert metrics.get("mod_disk") == 0


def test_aux_k30_m3_wave_names() -> None:
    """Staging manifest object names must match the active wave snapshot.

    Fails when manifest lists a subset of active_wave.json objects or adds extras.
    """
    _rebuild("cold")
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert manifest_names == _active_wave_names()


def test_aux_k31_m7_warm_disk() -> None:
    """Warm profile must keep unstaged mod_disk at avail_metric 0.

    Fails when warm trace treats every weight-table row as available regardless of manifest membership.
    """
    _rebuild("warm")
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    assert metrics.get("mod_disk") == 0


def test_aux_k32_m5_epoch_seq() -> None:
    """Journal segment epoch fields must be a contiguous 1-based sequence.

    Fails when epoch numbering skips values or restarts mid-journal.
    """
    _rebuild("cold", merge=True)
    epochs = [seg["epoch"] for seg in _load_journal()["segments"]]
    assert epochs == list(range(1, len(epochs) + 1))


def test_aux_k33_m3_merge_count() -> None:
    """Merged cold manifest must contain six wave objects.

    Fails when incremental merge drops parent-wave modules from staging_manifest.
    """
    _rebuild("cold", merge=True)
    assert len(_load_manifest()["objects"]) == 6


def test_aux_k34_m1_parent_count() -> None:
    """Plain cold manifest must contain five parent-wave objects only.

    Fails when non-merge runs pull delta-only modules into staging_manifest.
    """
    _rebuild("cold")
    assert len(_load_manifest()["objects"]) == 5


def test_aux_k35_m3_active_carry() -> None:
    """Active wave snapshot must record WAVE_B carry after incremental merge.

    Fails when merge staging keeps the parent carry token in active_wave.json.
    """
    _rebuild("cold", merge=True)
    wave = _load_json(STAGING_WAVE)
    assert wave["carry_token"] == "WAVE_B"


def test_aux_k36_m4_hook_epoch() -> None:
    """Hook commit rows must record hook_epoch 1 from the driver scheduler.

    Fails when exec_w0 passes a zero hook_epoch into the hook gate helper.
    """
    _rebuild("cold")
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    assert all(row["hook_epoch"] == 1 for row in hook["commits"])


def test_aux_k37_m5_blob_mono() -> None:
    """Journal blob_epoch must never decrease between segments.

    Fails when O-lane emission resets or decrements the blob counter.
    """
    _rebuild("cold", merge=True)
    blob_epochs = [seg["blob_epoch"] for seg in _load_journal()["segments"]]
    for prev, cur in zip(blob_epochs, blob_epochs[1:]):
        assert cur >= prev


def test_aux_k38_m4_alpha() -> None:
    """Cold fw_alpha avail_metric must follow hook_state gating.

    Fails when trace rows ignore hook_state when marking B-lane required objects.
    """
    _rebuild("cold")
    trace = _load_trace()
    parity = _parity("cold")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    alpha = next(row for row in trace["rows"] if row["object"] == "fw_alpha")
    assert alpha["avail_metric"] == parity_by_object["fw_alpha"]["avail_metric"]


def test_aux_k39_m1_warm_repeat() -> None:
    """Warm read_order must be stable across consecutive driver runs.

    Fails when warm rebuild reshuffles weight-table ordering between identical invocations.
    """
    _clear_outputs()
    _run_warm()
    first = _load_trace()["read_order"]
    _run_warm()
    second = _load_trace()["read_order"]
    assert first == second


def test_aux_k40_m5_lane_presence() -> None:
    """Merged journal must include both B-lane and O-lane segments.

    Fails when merge journal emission drops an entire lane present in the active wave.
    """
    _rebuild("cold", merge=True)
    lanes = {seg["lane"] for seg in _load_journal()["segments"]}
    assert lanes == VALID_LANES


def test_aux_k41_m4_b_commit() -> None:
    """B-lane hook commit must be true on cold non-merge runs.

    Fails when the hook gate never commits blob-lane rows even when blob_epoch equals hook_gen.
    """
    _rebuild("cold")
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    journal = _load_journal()
    b_commit = next(
        commit for commit, seg in zip(hook["commits"], journal["segments"]) if seg["lane"] == "B"
    )
    assert b_commit["committed"] is True


def test_aux_k42_m7_warm_req() -> None:
    """Warm CLEAN status requires every warm required object at avail_metric 1.

    Fails when status_token is CLEAN while a warm required object remains gated off.
    """
    _rebuild("warm")
    trace = _load_trace()
    required = PROFILES["profiles"]["warm"]["required"]
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if trace["status_token"] == "CLEAN":
        assert all(metrics.get(name, 0) == 1 for name in required)


def test_aux_k43_m3_merge_dirty() -> None:
    """Cold merge with premature O-lane hook commit must not report CLEAN.

    Fails when merge runs mark status CLEAN while mod_disk or other required objects stay gated.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    required = PROFILES["profiles"]["cold"]["required"]
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if any(metrics.get(name, 0) == 0 for name in required):
        assert trace["status_token"] == "DIRTY"


def test_aux_k44_m2_chroot_only() -> None:
    """Chroot index order must match host index order after merge.

    Fails when host index follows weight order but chroot index falls back to name sort.
    """
    _rebuild("cold", merge=True)
    host = _load_json(Path("/app/.staging/host_index.json"))["order"]
    chroot = _load_json(Path("/app/.staging/chroot_index.json"))["order"]
    expected = _weight_order("cold", list(_active_wave_names()))
    assert chroot == expected
    assert host == chroot


def test_aux_k45_m5_o_objects() -> None:
    """O-lane journal segment must list every O-lane object from the active wave.

    Fails when journal emission reads the delta bundle instead of the merged active wave.
    """
    _rebuild("cold", merge=True)
    wave = _load_json(STAGING_WAVE)
    o_expected = {o["name"] for o in wave["objects"] if o["lane"] == "O"}
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert set(o_seg["objects"]) == o_expected


def test_aux_k46_m2_tie_cold() -> None:
    """Cold read_order must break equal weights by ascending object name.

    Fails when mod_rtc sorts ahead of mod_net despite sharing weight 40 on the cold table.
    """
    _rebuild("cold")
    order = _load_trace()["read_order"]
    assert order.index("mod_net") < order.index("mod_rtc")


def test_aux_k47_m1_rtc_parent() -> None:
    """Plain cold manifest must include parent-wave mod_rtc.

    Fails when wave_a objects are dropped from staging_manifest on non-merge runs.
    """
    _rebuild("cold")
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_rtc" in manifest_names


def test_aux_k48_m3_rtc_merge() -> None:
    """Merged cold manifest must retain mod_rtc alongside delta modules.

    Fails when incremental merge drops parent B-lane modules such as mod_rtc.
    """
    _rebuild("cold", merge=True)
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_rtc" in manifest_names


def test_aux_k49_m5_b_objects() -> None:
    """B-lane journal segment must list every B-lane object from the active wave.

    Fails when journal emission omits mod_rtc from the blob-lane segment object list.
    """
    _rebuild("cold")
    wave = _load_json(STAGING_WAVE)
    b_expected = {o["name"] for o in wave["objects"] if o["lane"] == "B"}
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert set(b_seg["objects"]) == b_expected


def test_aux_k50_m7_hook_start() -> None:
    """First journal segment hook_gen must be 1, not copied from blob_epoch alone.

    Fails when B-lane emission writes hook_gen equal to blob_epoch instead of the independent counter.
    """
    _rebuild("cold")
    first = _load_journal()["segments"][0]
    assert first["hook_gen"] == 1


def test_aux_k51_m5_b_count() -> None:
    """Cold B-lane segment must stage three blob-lane objects.

    Fails when fw_alpha, fw_beta, and mod_rtc are not grouped in the B-lane journal row.
    """
    _rebuild("cold")
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert len(b_seg["objects"]) == 3


def test_aux_k52_m2_tie_warm() -> None:
    """Warm read_order must place mod_rtc after mod_net by weight then name.

    Fails when warm loader_trace ignores descending-weight ordering for mod_rtc and mod_net.
    """
    _rebuild("warm")
    order = _load_trace()["read_order"]
    assert order.index("mod_net") < order.index("mod_rtc")


def test_aux_k53_m3_rtc_stamp() -> None:
    """Merge stamp must digest sorted names including mod_rtc with WAVE_B carry.

    Fails when stamp hashing uses wave insertion order instead of sorted object names.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_B")


def test_aux_k54_m6_rtc_row() -> None:
    """Loader trace must emit a schema-valid row for mod_rtc.

    Fails when trace emission skips weight-table objects present in the active wave.
    """
    _rebuild("cold")
    rtc = next(row for row in _load_trace()["rows"] if row["object"] == "mod_rtc")
    assert _row_matches_schema(rtc)


def test_aux_k55_m4_rtc_warm() -> None:
    """Warm mod_rtc avail_metric must follow hook_state gating.

    Fails when warm trace marks mod_rtc available without hook_state lane alignment.
    """
    _rebuild("warm")
    trace = _load_trace()
    parity = _parity("warm")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    rtc = next(row for row in trace["rows"] if row["object"] == "mod_rtc")
    assert rtc["avail_metric"] == parity_by_object["mod_rtc"]["avail_metric"]


def test_aux_k56_m3_merge_repeat() -> None:
    """Second incremental merge run must keep WAVE_B carry in active wave.

    Fails when repeat merge runs revert active_wave carry_token to the parent value.
    """
    _rebuild("cold", merge=True)
    _run_cold(merge=True)
    wave = _load_json(STAGING_WAVE)
    assert wave["carry_token"] == "WAVE_B"


def test_aux_k57_m6_beta_lane() -> None:
    """Loader trace row for fw_beta must record B lane membership.

    Fails when trace assigns the wrong lane label to blob-lane objects.
    """
    _rebuild("cold")
    beta = next(row for row in _load_trace()["rows"] if row["object"] == "fw_beta")
    assert beta["lane"] == "B"


def test_aux_k58_m1_rtc_order() -> None:
    """Cold read_order must rank mod_rtc by weight-table position.

    Fails when mod_rtc is sorted lexicographically ahead of heavier modules.
    """
    _rebuild("cold")
    order = _load_trace()["read_order"]
    assert order.index("mod_core") < order.index("mod_rtc")


def test_aux_k59_m3_rtc_journal() -> None:
    """Merged journal B segment must include mod_rtc with parent blob-lane objects.

    Fails when merge journal emission reads only the delta bundle for B-lane names.
    """
    _rebuild("cold", merge=True)
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert "mod_rtc" in b_seg["objects"]


def test_aux_k60_m5_warm_count() -> None:
    """Warm manifest must contain five parent-wave objects.

    Fails when warm rebuild drops mod_rtc or other wave_a modules from staging_manifest.
    """
    _rebuild("warm")
    assert len(_load_manifest()["objects"]) == 5


def _lane_weight_order(profile: str, names: list[str]) -> list[str]:
    weights = _weights(profile)
    return sorted(names, key=lambda n: (-weights[n], n))


def _lane_objects(journal: dict, lane: str) -> list[str]:
    segment = next(seg for seg in journal["segments"] if seg["lane"] == lane)
    return segment["objects"]


def _wave_lane_names(lane: str) -> list[str]:
    wave = _load_json(STAGING_WAVE)
    return [o["name"] for o in wave["objects"] if o["lane"] == lane]


def _load_ledger() -> dict:
    return _load_json(Path("/app/.staging/epoch_ledger.json"))


def _run_sequence(*steps: tuple[str, bool, int]) -> None:
    _clear_outputs()
    for profile, merge, merge_tier in steps:
        if profile == "cold":
            _run_cold(merge=merge, merge_tier=merge_tier)
        else:
            _run_warm()


def test_aux_k61_m4_warm_then_cold() -> None:
    """Warm then cold in one session must leave cold profile on final manifest.

    Fails when profile-specific staging state from the warm run bleeds into cold outputs.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0))
    assert _load_manifest()["profile"] == "cold"


def test_aux_k62_m2_cold_after_merge_reset() -> None:
    """Plain cold after merge must revert carry to WAVE_A with five objects.

    Fails when merge carry token or delta object count persists into a non-merge cold run.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 0))
    manifest = _load_manifest()
    assert manifest["carry"] == "WAVE_A"
    assert len(manifest["objects"]) == 5


def test_aux_k63_m3_cold_then_merge() -> None:
    """Cold non-merge followed by merge must adopt WAVE_B carry.

    Fails when a stale carry token from the first cold run pins WAVE_A during incremental merge.
    """
    _run_sequence(("cold", False, 0), ("cold", True, 0))
    assert _load_manifest()["carry"] == "WAVE_B"


def test_aux_k64_m5_mod_core_merge() -> None:
    """Merged cold journal O-lane segment must include mod_core.

    Fails when merge journal reads only the delta bundle for object-lane names.
    """
    _rebuild("cold", merge=True)
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert "mod_core" in o_seg["objects"]


def test_aux_k65_m4_fw_beta_merge() -> None:
    """Merged cold fw_beta must reach avail_metric 1 when hooks gate correctly.

    Fails when merge rebuild leaves B-lane required objects gated off despite staging.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    beta = next(row for row in trace["rows"] if row["object"] == "fw_beta")
    assert beta["avail_metric"] == 1


def test_aux_k66_m3_mod_core_avail() -> None:
    """Merged cold mod_core must reach avail_metric 1 via O-lane B-lane inheritance.

    Fails when O-lane avail ignores inherited B-lane hook commits after merge.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k67_m7_hook_gen_floor() -> None:
    """Every journal segment hook_gen must be at least 1.

    Fails when hook generation copies blob_epoch zero or emits non-positive hook_gen.
    """
    _rebuild("cold", merge=True)
    assert all(seg["hook_gen"] >= 1 for seg in _load_journal()["segments"])


def test_aux_k68_m4_rerun_stamp() -> None:
    """Two consecutive cold runs must produce identical manifest stamps.

    Fails when rerun rebuild drifts stamp digests despite an unchanged active wave.
    """
    _clear_outputs()
    _run_cold()
    first = _load_manifest()["stamp"]
    _run_cold()
    second = _load_manifest()["stamp"]
    assert first == second


def test_aux_k69_m1_warm_cold_order() -> None:
    """Warm-then-cold session must end with cold weight-table read_order.

    Fails when warm read_order persists in loader_trace after a cold driver run.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0))
    trace = _load_trace()
    expected = _weight_order("cold", list(_weights("cold").keys()))
    assert trace["read_order"] == expected


def test_aux_k70_m3_merge_manifest_carry_wave() -> None:
    """Merge manifest carry must match active_wave carry_token.

    Fails when stale carry resolution or parent defaults override the merged active wave snapshot.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    wave = _load_json(STAGING_WAVE)
    assert manifest["carry"] == wave["carry_token"]


def test_aux_k71_m5_o_count_merge() -> None:
    """Merged O-lane journal segment must stage three object-lane modules.

    Fails when merge journal lists only the delta mod_disk in the O-lane row.
    """
    _rebuild("cold", merge=True)
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert len(o_seg["objects"]) == 3


def test_aux_k72_m2_warm_after_cold() -> None:
    """Cold then warm in one session must restore warm manifest object count.

    Fails when cold merge residue leaves six objects in a subsequent warm rebuild.
    """
    _run_sequence(("cold", True, 0), ("warm", False, 0))
    assert len(_load_manifest()["objects"]) == 5


def test_aux_k73_m6_alpha_lane_merge() -> None:
    """Merged cold loader trace must label fw_alpha as B-lane.

    Fails when merge trace emission assigns incorrect lane labels to blob-lane objects.
    """
    _rebuild("cold", merge=True)
    alpha = next(row for row in _load_trace()["rows"] if row["object"] == "fw_alpha")
    assert alpha["lane"] == "B"


def test_aux_k74_m1_b_epoch_one() -> None:
    """First B-lane segment blob_epoch must be 1 on cold non-merge runs.

    Fails when blob counter never increments before the first blob-lane journal row.
    """
    _rebuild("cold")
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert b_seg["blob_epoch"] == 1


def test_aux_k75_m3_merge_hook_commits() -> None:
    """Merged cold hook_state must record one commit row per journal segment.

    Fails when merge hook scheduling drops commit metadata for delta segments.
    """
    _rebuild("cold", merge=True)
    journal = _load_journal()
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    assert len(hook["commits"]) == len(journal["segments"])


def test_aux_k76_m3_tier2_carry() -> None:
    """Second-tier merge must adopt WAVE_C carry token.

    Fails when tier-2 staging keeps WAVE_B or WAVE_A instead of wave_c carry_token.
    """
    _rebuild("cold", merge_tier=2)
    assert _load_manifest()["carry"] == "WAVE_C"


def test_aux_k77_m3_tier2_count() -> None:
    """Tier-2 merged cold manifest must contain seven wave objects.

    Fails when wave_c merge drops mod_disk or other tier-1 modules from staging_manifest.
    """
    _rebuild("cold", merge_tier=2)
    assert len(_load_manifest()["objects"]) == 7


def test_aux_k78_m3_sensor_present() -> None:
    """Tier-2 merge must stage mod_sensor from wave_c.json.

    Fails when tier-2 rebuild omits mod_sensor despite wave_c delta bundle.
    """
    _rebuild("cold", merge_tier=2)
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_sensor" in manifest_names


def test_aux_k79_m3_sensor_absent_tier1() -> None:
    """Tier-1 merge must not include mod_sensor before wave_c applies.

    Fails when first merge pulls wave_c objects into staging_manifest early.
    """
    _rebuild("cold", merge=True)
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_sensor" not in manifest_names


def test_aux_k80_m1_sensor_absent_plain() -> None:
    """Plain cold manifest must not list mod_sensor.

    Fails when non-merge runs stage wave_c-only modules without --merge-tier 2.
    """
    _rebuild("cold")
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_sensor" not in manifest_names


def test_aux_k81_m4_sensor_avail() -> None:
    """Tier-2 cold mod_sensor must reach avail_metric 1 when hooks gate correctly.

    Fails when mod_sensor is staged but loader_trace still reports unavailable.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    assert metrics.get("mod_sensor") == 1


def test_aux_k82_m5_sensor_journal() -> None:
    """Tier-2 journal O-lane segment must list mod_sensor with other O-lane objects.

    Fails when journal emission omits wave_c object-lane names from the O segment.
    """
    _rebuild("cold", merge_tier=2)
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert "mod_sensor" in o_seg["objects"]


def test_aux_k83_m7_rev_bump_tier2() -> None:
    """Tier-2 merge must increment epoch ledger rev when stamp changes.

    Fails when epoch ledger rev always increments or never records tier-2 stamp changes.
    """
    _clear_outputs()
    _run_cold(merge=True)
    rev_after_tier1 = _load_ledger()["rev"]
    _run_cold(merge_tier=2)
    assert _load_ledger()["rev"] == rev_after_tier1 + 1


def test_aux_k84_m8_rev_stable_rerun() -> None:
    """Identical cold reruns must leave epoch ledger rev unchanged.

    Fails when rev increments on every driver run regardless of stamp stability.
    """
    _clear_outputs()
    _run_cold()
    rev_first = _load_ledger()["rev"]
    _run_cold()
    assert _load_ledger()["rev"] == rev_first


def test_aux_k85_m3_disk_tier2() -> None:
    """Tier-2 merge must retain mod_disk from tier-1 alongside mod_sensor.

    Fails when tier-2 staging merges wave_a with wave_c only and drops mod_disk.
    """
    _rebuild("cold", merge_tier=2)
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert "mod_disk" in manifest_names


def test_aux_k86_m3_tier2_stamp() -> None:
    """Tier-2 stamp must digest sorted seven-object names with WAVE_C carry.

    Fails when tier-2 stamp binds WAVE_B carry or an incomplete object name set.
    """
    _rebuild("cold", merge_tier=2)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_C")


def test_aux_k87_m4_sensor_gated_tier1() -> None:
    """Tier-1 cold must report mod_sensor unavailable.

    Fails when loader_trace marks wave_c required objects available before tier-2 staging.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    assert metrics.get("mod_sensor") == 0


def test_aux_k88_m1_sensor_order() -> None:
    """Tier-2 read_order must include mod_sensor sorted by cold weight table.

    Fails when read_order omits mod_sensor or sorts it outside weight-table rules.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    expected = _weight_order("cold", list(_weights("cold").keys()))
    assert trace["read_order"] == expected
    assert "mod_sensor" in trace["read_order"]


def test_aux_k89_m3_seq_tier2() -> None:
    """Cold then tier-1 merge then tier-2 merge must end on WAVE_C carry.

    Fails when chained merges reuse stale carry tokens from earlier driver runs.
    """
    _run_sequence(("cold", False, 0), ("cold", True, 0), ("cold", False, 2))
    manifest = _load_manifest()
    wave = _load_json(STAGING_WAVE)
    assert manifest["carry"] == "WAVE_C"
    assert wave["carry_token"] == "WAVE_C"


def test_aux_k90_m2_bind_tier2() -> None:
    """Tier-2 host and chroot index views must match weight-table order.

    Fails when tier-2 rebuild leaves chroot index on name sort with seven objects.
    """
    _rebuild("cold", merge_tier=2)
    _index_bind_check("cold")


def test_aux_k91_m5_o_count_tier2() -> None:
    """Tier-2 O-lane journal segment must stage four object-lane modules.

    Fails when tier-2 journal lists only mod_sensor without mod_core, mod_net, and mod_disk.
    """
    _rebuild("cold", merge_tier=2)
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert len(o_seg["objects"]) == 4


def test_aux_k92_m4_tier2_clean() -> None:
    """Tier-2 cold CLEAN status requires mod_sensor and mod_disk available.

    Fails when tier-2 rebuild reports CLEAN while wave_c required objects stay gated.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    required = PROFILES["profiles"]["cold"]["required"]
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if trace["status_token"] == "CLEAN":
        assert all(metrics.get(name, 0) == 1 for name in required)


def test_aux_k93_m6_sensor_row() -> None:
    """Loader trace must emit a schema-valid row for mod_sensor on tier-2 cold.

    Fails when trace emission skips weight-table objects introduced by wave_c.
    """
    _rebuild("cold", merge_tier=2)
    sensor = next(row for row in _load_trace()["rows"] if row["object"] == "mod_sensor")
    assert _row_matches_schema(sensor)
    assert sensor["lane"] == "O"


def test_aux_k94_m3_active_wave_tier2() -> None:
    """Active wave snapshot must record WAVE_C carry after tier-2 merge.

    Fails when tier-2 staging writes WAVE_B into active_wave.json carry_token.
    """
    _rebuild("cold", merge_tier=2)
    wave = _load_json(STAGING_WAVE)
    assert wave["carry_token"] == "WAVE_C"


def test_aux_k95_m7_hook_gen_tier2() -> None:
    """Tier-2 journal hook_gen values must remain strictly increasing.

    Fails when extra merge tier reuses hook_gen from blob_epoch on O-lane rows.
    """
    _rebuild("cold", merge_tier=2)
    gens = [seg["hook_gen"] for seg in _load_journal()["segments"]]
    assert gens == sorted(gens)
    assert len(gens) == len(set(gens))


def test_aux_k96_m8_last_stamp_bump() -> None:
    """Epoch ledger last_stamp must track manifest stamp after tier-2 bump.

    Fails when epoch ledger records a stale last_stamp after stamp changes on tier-2 merge.
    """
    _clear_outputs()
    _run_cold(merge=True)
    _run_cold(merge_tier=2)
    manifest = _load_manifest()
    ledger = _load_ledger()
    assert ledger["last_stamp"] == manifest["stamp"]


def test_aux_k97_m8_last_stamp_stable() -> None:
    """Identical cold reruns must keep last_stamp aligned with manifest stamp.

    Fails when repeat runs drift last_stamp even though manifest stamp is unchanged.
    """
    _clear_outputs()
    _run_cold()
    ledger = _load_ledger()
    manifest = _load_manifest()
    assert ledger["last_stamp"] == manifest["stamp"]
    _run_cold()
    assert _load_ledger()["last_stamp"] == _load_manifest()["stamp"]


def test_aux_k98_m2_index_len_cold() -> None:
    """Plain cold index order must list only five active-wave objects.

    Fails when index views include weight-table rows outside the active wave snapshot.
    """
    _rebuild("cold")
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    chroot = _load_json(APP / ".staging" / "chroot_index.json")["order"]
    assert len(host) == 5
    assert len(chroot) == 5
    assert "mod_disk" not in host


def test_aux_k99_m2_index_len_merge() -> None:
    """Tier-1 merge index order must list six active-wave objects.

    Fails when merge rebuild leaves five-name index lists or omits mod_disk from order.
    """
    _rebuild("cold", merge=True)
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    assert len(host) == 6
    assert "mod_disk" in host
    assert "mod_sensor" not in host


def test_aux_k100_m2_index_len_tier2() -> None:
    """Tier-2 merge index order must list seven active-wave objects.

    Fails when tier-2 rebuild omits mod_sensor or drops tier-1 modules from index order.
    """
    _rebuild("cold", merge_tier=2)
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    assert len(host) == 7
    assert "mod_sensor" in host
    assert "mod_disk" in host


def test_aux_k101_m5_warm_carry_wave() -> None:
    """Warm manifest carry must match active_wave carry_token.

    Fails when warm staging reads a cached carry instead of the live wave snapshot.
    """
    _rebuild("warm")
    manifest = _load_manifest()
    wave = _load_json(STAGING_WAVE)
    assert manifest["carry"] == wave["carry_token"]


def test_aux_k102_m4_tier2_status() -> None:
    """Tier-2 loader status_token must reflect required-object avail aggregation.

    Fails when tier-2 rebuild reports CLEAN while wave_c required objects stay gated.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    assert trace["status_token"] == _derived_status("cold", trace["rows"])


def test_aux_k103_m3_tier2_journal_union() -> None:
    """Tier-2 journal object union must match seven-object active wave.

    Fails when tier-2 journal emission drops parent or delta modules from segment lists.
    """
    _rebuild("cold", merge_tier=2)
    staged = _journal_object_names(_load_journal())
    assert staged == _active_wave_names()
    assert len(staged) == 7


def test_aux_k104_m4_rev_after_warm_cold() -> None:
    """Profile switch warm to cold must bump rev when manifest stamp changes.

    Fails when epoch ledger ignores stamp changes across profile switches in one session.
    """
    _clear_outputs()
    _run_warm()
    rev_warm = _load_ledger()["rev"]
    _run_cold()
    rev_cold = _load_ledger()["rev"]
    assert rev_cold == rev_warm + 1


def test_aux_k105_m6_tier2_hook_commits() -> None:
    """Tier-2 hook_state must commit B-lane while O-lane stays uncommitted on cold path.

    Fails when tier-2 hook scheduling commits both lanes before blob_epoch equals hook_gen.
    """
    _rebuild("cold", merge_tier=2)
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    journal = _load_journal()
    b_commit = next(
        commit for commit, seg in zip(hook["commits"], journal["segments"]) if seg["lane"] == "B"
    )
    o_commit = next(
        commit for commit, seg in zip(hook["commits"], journal["segments"]) if seg["lane"] == "O"
    )
    assert b_commit["committed"] is True
    assert o_commit["committed"] is False


def test_aux_k106_m3_tier2_then_plain() -> None:
    """Tier-2 merge followed by plain cold must revert to WAVE_A carry and five objects.

    Fails when tier-2 carry token or seven-object snapshot persists into a non-merge cold run.
    """
    _run_sequence(("cold", False, 2), ("cold", False, 0))
    manifest = _load_manifest()
    assert manifest["carry"] == "WAVE_A"
    assert len(manifest["objects"]) == 5
    assert "mod_sensor" not in {o["name"] for o in manifest["objects"]}


def test_aux_k107_m1_sensor_weight_order() -> None:
    """Tier-2 read_order must place mod_sensor after mod_rtc by descending weight tie-break.

    Fails when mod_sensor sorts ahead of heavier modules or is omitted from read_order.
    """
    _rebuild("cold", merge_tier=2)
    order = _load_trace()["read_order"]
    assert order.index("mod_rtc") < order.index("mod_sensor")
    assert order.index("mod_disk") < order.index("mod_sensor")


def test_aux_k108_m8_tier2_stamp_stable() -> None:
    """Identical tier-2 merge reruns must keep manifest stamp and epoch ledger rev stable.

    Fails when repeat tier-2 runs drift stamp digests or bump rev without stamp change.
    """
    _clear_outputs()
    _run_cold(merge_tier=2)
    stamp_first = _load_manifest()["stamp"]
    rev_first = _load_ledger()["rev"]
    _run_cold(merge_tier=2)
    assert _load_manifest()["stamp"] == stamp_first
    assert _load_ledger()["rev"] == rev_first


def test_aux_k109_m3_merge_then_tier2_count() -> None:
    """Chained tier-1 merge then tier-2 merge must end with seven active-wave objects.

    Fails when tier-2 staging drops tier-1 mod_disk or parent-wave modules from active_wave.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    wave_names = _active_wave_names()
    assert len(wave_names) == 7
    assert "mod_disk" in wave_names
    assert "mod_sensor" in wave_names
    assert "mod_rtc" in wave_names


def test_aux_k110_m4_tier2_dirty_until_hooks() -> None:
    """Tier-2 cold with premature O-lane hook commit must not report CLEAN while mod_sensor gated.

    Fails when tier-2 rebuild marks CLEAN while wave_c required objects remain at avail_metric 0.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if metrics.get("mod_sensor", 0) == 0:
        assert trace["status_token"] == "DIRTY"


def test_aux_k111_m5_tier2_b_objects() -> None:
    """Tier-2 journal B-lane segment must list three blob-lane parent modules.

    Fails when tier-2 journal emission drops mod_rtc or other B-lane names from the merged wave.
    """
    _rebuild("cold", merge_tier=2)
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert set(b_seg["objects"]) == {"fw_alpha", "fw_beta", "mod_rtc"}


def test_aux_k112_m7_tier2_hook_gen_start() -> None:
    """Tier-2 first journal segment hook_gen must be 1 on the cold merge path.

    Fails when tier-2 journal reuses hook_gen from a prior session instead of resetting counters.
    """
    _rebuild("cold", merge_tier=2)
    first = _load_journal()["segments"][0]
    assert first["hook_gen"] == 1


def test_aux_k113_m2_warm_after_tier2() -> None:
    """Warm rebuild after tier-2 cold session must restore five-object warm manifest.

    Fails when tier-2 residue leaves mod_sensor or mod_disk in warm staging_manifest.
    """
    _run_sequence(("cold", False, 2), ("warm", False, 0))
    manifest_names = {o["name"] for o in _load_manifest()["objects"]}
    assert len(manifest_names) == 5
    assert "mod_sensor" not in manifest_names
    assert "mod_disk" not in manifest_names


def test_aux_k114_m6_tier2_rowcount() -> None:
    """Tier-2 loader trace must emit one row per cold weight-table object.

    Fails when trace rows omit mod_sensor or other weight-table entries after tier-2 staging.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    assert len(trace["rows"]) == len(_weights("cold"))


def test_aux_k115_m8_tier2_rev_after_plain() -> None:
    """Plain cold after tier-2 must bump rev when stamp changes back to parent fingerprint.

    Fails when epoch ledger ignores stamp transitions from tier-2 back to plain cold carry.
    """
    _clear_outputs()
    _run_cold(merge_tier=2)
    rev_tier2 = _load_ledger()["rev"]
    _run_cold()
    assert _load_ledger()["rev"] == rev_tier2 + 1
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k116_m4_warm_double_stamp() -> None:
    """Two consecutive warm runs must keep manifest stamp and epoch ledger rev stable.

    Fails when warm reruns drift stamp digests or bump rev without stamp change.
    """
    _clear_outputs()
    _run_warm()
    stamp_first = _load_manifest()["stamp"]
    rev_first = _load_ledger()["rev"]
    _run_warm()
    assert _load_manifest()["stamp"] == stamp_first
    assert _load_ledger()["rev"] == rev_first


def test_aux_k117_m3_merge_then_warm_carry() -> None:
    """Cold merge followed by warm must restore WAVE_A carry on the warm manifest.

    Fails when merge carry token bleeds into a subsequent warm rebuild.
    """
    _run_sequence(("cold", True, 0), ("warm", False, 0))
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k118_m5_tier2_b_blob_epoch() -> None:
    """Tier-2 first B-lane segment blob_epoch must be 1.

    Fails when blob counter never increments before the first blob-lane journal row on tier-2.
    """
    _rebuild("cold", merge_tier=2)
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    assert b_seg["blob_epoch"] == 1


def test_aux_k119_m6_tier2_hook_epoch() -> None:
    """Tier-2 hook commit rows must record hook_epoch 1 from the driver scheduler.

    Fails when tier-2 hook scheduling passes a zero hook_epoch into commit metadata.
    """
    _rebuild("cold", merge_tier=2)
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    assert all(row["hook_epoch"] == 1 for row in hook["commits"])


def test_aux_k120_m4_warm_beta_parity() -> None:
    """Warm fw_beta avail_metric must follow hook_state gating rules.

    Fails when warm trace marks fw_beta available without hook_state lane alignment.
    """
    _rebuild("warm")
    trace = _load_trace()
    parity = _parity("warm")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    beta = next(row for row in trace["rows"] if row["object"] == "fw_beta")
    assert beta["avail_metric"] == parity_by_object["fw_beta"]["avail_metric"]


def test_aux_k121_m3_merge_alpha_avail() -> None:
    """Merged cold fw_alpha must reach avail_metric 1 when hooks gate correctly.

    Fails when merge rebuild leaves B-lane required objects gated off despite staging.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    alpha = next(row for row in trace["rows"] if row["object"] == "fw_alpha")
    assert alpha["avail_metric"] == 1


def test_aux_k122_m2_merge_index_len() -> None:
    """Tier-1 merge index order must list six active-wave objects sorted by weight.

    Fails when merge rebuild leaves five-name index lists or omits mod_disk from order.
    """
    _rebuild("cold", merge=True)
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    expected = _weight_order("cold", list(_active_wave_names()))
    assert len(host) == 6
    assert host == expected


def test_aux_k123_m8_warm_cold_rev_chain() -> None:
    """Warm, cold, and merge in one session must bump rev only when stamp changes.

    Fails when epoch ledger ignores stamp transitions across profile and merge switches.
    """
    _clear_outputs()
    _run_warm()
    rev_warm = _load_ledger()["rev"]
    _run_cold()
    rev_cold = _load_ledger()["rev"]
    _run_cold(merge=True)
    rev_merge = _load_ledger()["rev"]
    assert rev_cold == rev_warm + 1
    assert rev_merge == rev_cold + 1


def test_aux_k124_m7_tier2_o_blob_epoch() -> None:
    """Tier-2 O-lane segment must inherit blob_epoch from B-lane without advancing it.

    Fails when O-lane emission increments blob_epoch past the B-lane value on tier-2.
    """
    _rebuild("cold", merge_tier=2)
    b_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "B")
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert o_seg["blob_epoch"] == b_seg["blob_epoch"]


def test_aux_k125_m3_tier2_manifest_sensor() -> None:
    """Tier-2 staging manifest must list mod_sensor with WAVE_C carry.

    Fails when tier-2 manifest omits wave_c object or keeps tier-1 carry token.
    """
    _rebuild("cold", merge_tier=2)
    manifest = _load_manifest()
    manifest_names = {o["name"] for o in manifest["objects"]}
    assert manifest["carry"] == "WAVE_C"
    assert "mod_sensor" in manifest_names


def test_aux_k126_m4_core_inherit_plain() -> None:
    """Plain cold mod_core must reach avail_metric 1 via B-lane hook inheritance.

    Fails when availability logic requires O-lane hook commit instead of inheriting blob-lane success.
    """
    _rebuild("cold")
    trace = _load_trace()
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k127_m4_net_not_required_cold() -> None:
    """Plain cold mod_net must stay at avail_metric 0 when it is outside the required set.

    Fails when availability logic marks every staged object available regardless of required membership.
    """
    _rebuild("cold")
    trace = _load_trace()
    net = next(row for row in trace["rows"] if row["object"] == "mod_net")
    assert net["avail_metric"] == 0


def test_aux_k128_m4_sensor_inherit_tier2() -> None:
    """Tier-2 mod_sensor must reach avail_metric 1 when B-lane hook commits.

    Fails when availability logic requires O-lane hook commit for wave_c object-lane modules.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    sensor = next(row for row in trace["rows"] if row["object"] == "mod_sensor")
    assert sensor["avail_metric"] == 1


def test_aux_k129_m4_disk_inherit_merge() -> None:
    """Merged cold mod_disk must reach avail_metric 1 via inherited blob-lane commit.

    Fails when availability logic ignores B-lane inheritance for delta object-lane modules.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    disk = next(row for row in trace["rows"] if row["object"] == "mod_disk")
    assert disk["avail_metric"] == 1


def test_aux_k130_m7_metric_rows_match_parity() -> None:
    """Every cold merge loader row avail_metric must match hook-gated parity expectations.

    Fails when availability logic computes availability without blob-lane inheritance for O-lane rows.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    parity = _parity("cold")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    for row in trace["rows"]:
        if row["object"] in PROFILES["profiles"]["cold"]["required"]:
            assert row["avail_metric"] == parity_by_object[row["object"]]["avail_metric"]


def test_aux_k131_m4_warm_core_inherit() -> None:
    """Warm mod_core must reach avail_metric 1 when B-lane hook commits on warm path.

    Fails when availability logic marks O-lane warm modules unavailable despite blob-lane success.
    """
    _rebuild("warm")
    trace = _load_trace()
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k132_m7_tier2_dirty_if_sensor_gated() -> None:
    """Tier-2 DIRTY status must appear when mod_sensor stays at avail_metric 0.

    Fails when loader emission forces CLEAN while availability logic leaves wave_c required objects gated.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if metrics.get("mod_sensor", 0) == 0:
        assert trace["status_token"] == "DIRTY"


def test_aux_k133_m4_beta_plain_cold() -> None:
    """Plain cold fw_beta must reach avail_metric 1 when B-lane hook commits.

    Fails when availability logic drops blob-lane availability even when hook_state commits B lane.
    """
    _rebuild("cold")
    trace = _load_trace()
    beta = next(row for row in trace["rows"] if row["object"] == "fw_beta")
    assert beta["avail_metric"] == 1


def test_aux_k134_m3_merge_status_dirty() -> None:
    """Cold merge with O-lane hook uncommitted must report DIRTY until inheritance applies.

    Fails when loader emission reports CLEAN while availability logic leaves required O-lane objects gated.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    hook = _load_json(Path("/app/.staging/hook_state.json"))
    journal = _load_journal()
    o_commit = next(
        commit for commit, seg in zip(hook["commits"], journal["segments"]) if seg["lane"] == "O"
    )
    if not o_commit["committed"]:
        required = PROFILES["profiles"]["cold"]["required"]
        metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
        if any(metrics.get(name, 0) == 0 for name in required):
            assert trace["status_token"] == "DIRTY"


def test_aux_k135_m6_tier2_core_row() -> None:
    """Tier-2 loader trace must emit schema-valid mod_core row with inherited availability.

    Fails when availability logic omits inheritance and leaves mod_core at avail_metric 0 on tier-2 cold.
    """
    _rebuild("cold", merge_tier=2)
    core = next(row for row in _load_trace()["rows"] if row["object"] == "mod_core")
    assert _row_matches_schema(core)
    assert core["avail_metric"] == 1


def test_aux_k136_m4_rtc_inherit_merge() -> None:
    """Merged cold mod_rtc must stay unavailable because it is not in the cold required set.

    Fails when availability logic marks non-required objects available without hook gating rules.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    rtc = next(row for row in trace["rows"] if row["object"] == "mod_rtc")
    assert rtc["avail_metric"] == 0


def test_aux_k137_m7_warm_metric_parity() -> None:
    """Warm loader rows must match hook-gated parity for every warm required object.

    Fails when availability logic uses lane-local commits only and drops B-lane inheritance on warm runs.
    """
    _rebuild("warm")
    trace = _load_trace()
    parity = _parity("warm")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    for name in PROFILES["profiles"]["warm"]["required"]:
        row = next(r for r in trace["rows"] if r["object"] == name)
        assert row["avail_metric"] == parity_by_object[name]["avail_metric"]


def test_aux_k138_m3_tier2_alpha_avail() -> None:
    """Tier-2 cold fw_alpha must reach avail_metric 1 on the blob-lane commit path.

    Fails when availability logic drops B-lane required availability after tier-2 staging completes.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    alpha = next(row for row in trace["rows"] if row["object"] == "fw_alpha")
    assert alpha["avail_metric"] == 1


def test_aux_k139_m4_plain_cold_status_dirty() -> None:
    """Plain cold loader status_token must be DIRTY when O-lane objects stay gated.

    Fails when loader emission forces CLEAN while availability logic leaves mod_core at avail_metric 0.
    """
    _rebuild("cold")
    trace = _load_trace()
    assert trace["status_token"] == "DIRTY"


def test_aux_k140_m8_metric_split_surface() -> None:
    """Cold merge read_order and row metrics must both come from corrected emit helpers.

    Fails when loader emission fixes read_order but availability logic still gates O-lane rows on O commit only.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    expected_order = _weight_order("cold", list(_weights("cold").keys()))
    assert trace["read_order"] == expected_order
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k141_m5_b_weight_order() -> None:
    """Cold B-lane journal objects must follow profile weight sort within the segment.

    Fails when journal emission keeps wave insertion order such as fw_alpha before mod_rtc on the cold table.
    """
    _rebuild("cold")
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("cold", b_names)


def test_aux_k142_m5_rtc_before_beta() -> None:
    """Cold B-lane journal must place mod_rtc ahead of fw_beta by descending weight.

    Fails when blob-lane object lists preserve wave_a insertion order instead of weight-table rank.
    """
    _rebuild("cold")
    order = _lane_objects(_load_journal(), "B")
    assert order.index("mod_rtc") < order.index("fw_beta")


def test_aux_k143_m5_merge_b_weight_order() -> None:
    """Merged cold B-lane journal objects must stay weight-sorted after incremental merge.

    Fails when merge journal emission preserves parent-wave insertion order inside the blob-lane row.
    """
    _rebuild("cold", merge=True)
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("cold", b_names)


def test_aux_k144_m5_tier2_b_weight_order() -> None:
    """Tier-2 cold B-lane journal objects must follow weight-table ordering.

    Fails when tier-2 journal emission lists fw_beta ahead of mod_rtc despite cold weights.
    """
    _rebuild("cold", merge_tier=2)
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("cold", b_names)


def test_aux_k145_m5_warm_b_weight_order() -> None:
    """Warm B-lane journal objects must follow warm profile weight ordering.

    Fails when warm journal emission sorts blob-lane names lexicographically instead of by warm weights.
    """
    _rebuild("warm")
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("warm", b_names)


def test_aux_k146_m5_merge_o_weight_order() -> None:
    """Merged cold O-lane journal objects must follow weight sort including mod_disk.

    Fails when object-lane lists keep delta insertion order with mod_disk ahead of mod_core.
    """
    _rebuild("cold", merge=True)
    journal = _load_journal()
    o_names = _wave_lane_names("O")
    assert _lane_objects(journal, "O") == _lane_weight_order("cold", o_names)


def test_aux_k147_m3_cache_tier2_carry() -> None:
    """Tier-2 merge after tier-1 in one session must adopt WAVE_C carry despite carry sidecars.

    Fails when carry sidecars pin WAVE_A or WAVE_B across merge-tier profile context changes.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    assert _load_manifest()["carry"] == "WAVE_C"


def test_aux_k148_m3_warm_after_merge_carry() -> None:
    """Warm rebuild after cold merge must restore WAVE_A carry from the parent wave snapshot.

    Fails when carry sidecars from the merge run bleed into a subsequent warm profile invocation.
    """
    _run_sequence(("cold", True, 0), ("warm", False, 0))
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k149_m5_tier2_o_weight_order() -> None:
    """Tier-2 O-lane journal must weight-sort mod_sensor with mod_core, mod_net, and mod_disk.

    Fails when tier-2 journal lists wave_c delta names before heavier parent object-lane modules.
    """
    _rebuild("cold", merge_tier=2)
    journal = _load_journal()
    o_names = _wave_lane_names("O")
    assert _lane_objects(journal, "O") == _lane_weight_order("cold", o_names)


def test_aux_k150_m5_o_weight_plain_cold() -> None:
    """Plain cold O-lane journal objects must follow weight sort for mod_core and mod_net.

    Fails when object-lane emission preserves wave insertion order when weights disagree.
    """
    _rebuild("cold")
    journal = _load_journal()
    o_names = _wave_lane_names("O")
    assert _lane_objects(journal, "O") == _lane_weight_order("cold", o_names)


def test_aux_k151_m3_cold_after_tier2_carry() -> None:
    """Plain cold after tier-2 in one session must not reuse tier-2 carry sidecars.

    Fails when carry sidecars keep WAVE_C after profile or merge tier context resets to plain cold.
    """
    _run_sequence(("cold", False, 2), ("cold", False, 0))
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k152_m5_warm_o_weight_order() -> None:
    """Warm O-lane journal objects must follow warm weight ordering for mod_core and mod_net.

    Fails when warm journal emission sorts object-lane names lexicographically.
    """
    _rebuild("warm")
    journal = _load_journal()
    o_names = _wave_lane_names("O")
    assert _lane_objects(journal, "O") == _lane_weight_order("warm", o_names)


def test_aux_k153_m3_merge_then_tier2_carry_active() -> None:
    """Chained tier-1 merge and tier-2 merge must record WAVE_C on active wave and manifest.

    Fails when carry sidecars from tier-1 block wave_c carry adoption on the second merge invocation.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    manifest = _load_manifest()
    wave = _load_json(STAGING_WAVE)
    assert manifest["carry"] == "WAVE_C"
    assert wave["carry_token"] == "WAVE_C"


def test_aux_k154_m5_alpha_before_beta_journal() -> None:
    """Cold B-lane journal must place fw_alpha ahead of fw_beta when weights rank alpha higher.

    Fails when journal emission reverses equal-rank blob-lane neighbors without applying weight sort.
    """
    _rebuild("cold")
    order = _lane_objects(_load_journal(), "B")
    assert order.index("fw_alpha") < order.index("fw_beta")


def test_aux_k155_m3_tier2_stamp_after_cache() -> None:
    """Tier-2 stamp must digest seven sorted names with WAVE_C after session carry cache invalidation.

    Fails when stale carry sidecars bind WAVE_B into the tier-2 manifest stamp body.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_C")


def _manifest_object_names() -> list[str]:
    return [o["name"] for o in _load_manifest()["objects"]]


def _expected_manifest_order(profile: str) -> list[str]:
    wave = _load_json(STAGING_WAVE)
    names = [o["name"] for o in wave["objects"]]
    return _lane_weight_order(profile, names)


def _trace_row_objects() -> list[str]:
    return [row["object"] for row in _load_trace()["rows"]]


def test_aux_k156_m6_manifest_order_cold() -> None:
    """Plain cold staging_manifest objects must follow profile weight ordering.

    Fails when manifest emission preserves wave_a insertion order instead of descending weight sort.
    """
    _rebuild("cold")
    assert _manifest_object_names() == _expected_manifest_order("cold")


def test_aux_k157_m6_manifest_order_merge() -> None:
    """Tier-1 merge manifest objects must follow cold weight ordering including mod_disk.

    Fails when merge manifest lists delta objects ahead of heavier parent modules.
    """
    _rebuild("cold", merge=True)
    assert _manifest_object_names() == _expected_manifest_order("cold")


def test_aux_k158_m6_manifest_order_tier2() -> None:
    """Tier-2 merge manifest objects must follow cold weight ordering across seven modules.

    Fails when tier-2 manifest preserves dict insertion order with mod_sensor misplaced.
    """
    _rebuild("cold", merge_tier=2)
    assert _manifest_object_names() == _expected_manifest_order("cold")


def test_aux_k159_m6_rows_match_read_order_cold() -> None:
    """Cold loader trace rows must follow read_order index-for-index.

    Fails when trace emission alphabetizes rows after computing weight-sorted read_order.
    """
    _rebuild("cold")
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k160_m6_rows_match_read_order_merge() -> None:
    """Merged cold loader rows must stay aligned with read_order sequence.

    Fails when merge trace sorts rows lexicographically despite corrected read_order.
    """
    _rebuild("cold", merge=True)
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k161_m6_rows_match_read_order_tier2() -> None:
    """Tier-2 loader rows must follow read_order including mod_sensor placement.

    Fails when tier-2 trace rows are emitted in name order instead of weight order.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k162_m6_rows_match_read_order_warm() -> None:
    """Warm loader trace rows must follow warm read_order sequence.

    Fails when warm trace alphabetizes rows after weight-sorted read_order is computed.
    """
    _rebuild("warm")
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k163_m6_manifest_order_warm() -> None:
    """Warm staging_manifest objects must follow warm profile weight ordering.

    Fails when warm manifest preserves wave insertion order for mod_core and mod_net.
    """
    _rebuild("warm")
    assert _manifest_object_names() == _expected_manifest_order("warm")


def test_aux_k164_m2_manifest_core_first_cold() -> None:
    """Plain cold manifest must list mod_core ahead of mod_net by weight rank.

    Fails when manifest object arrays keep wave insertion order with mod_net before mod_core.
    """
    _rebuild("cold")
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("mod_net")


def test_aux_k165_m6_manifest_rtc_before_beta() -> None:
    """Cold manifest must place mod_rtc ahead of fw_beta within blob-lane objects.

    Fails when manifest preserves wave_a insertion order inside the staged object list.
    """
    _rebuild("cold")
    names = _manifest_object_names()
    assert names.index("mod_rtc") < names.index("fw_beta")


def test_aux_k166_m3_manifest_disk_position_merge() -> None:
    """Merged manifest must place mod_disk after heavier mod_net and mod_rtc by weight.

    Fails when merge manifest appends delta objects ahead of parent modules with higher weights.
    """
    _rebuild("cold", merge=True)
    names = _manifest_object_names()
    assert names.index("mod_net") < names.index("mod_disk")
    assert names.index("mod_rtc") < names.index("mod_disk")


def test_aux_k167_m3_manifest_sensor_position_tier2() -> None:
    """Tier-2 manifest must place mod_sensor after mod_disk by cold weight ordering.

    Fails when tier-2 manifest lists wave_c delta ahead of tier-1 object-lane modules.
    """
    _rebuild("cold", merge_tier=2)
    names = _manifest_object_names()
    assert names.index("mod_disk") < names.index("mod_sensor")


def test_aux_k168_m4_rows_order_after_warm_cold() -> None:
    """Warm-then-cold session loader rows must match final cold read_order sequence.

    Fails when warm trace row ordering bleeds into a subsequent cold driver emission.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0))
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k169_m6_manifest_order_after_merge() -> None:
    """Second incremental merge must keep weight-sorted manifest objects with WAVE_B carry.

    Fails when repeat merge runs reorder manifest objects to wave bundle insertion order.
    """
    _rebuild("cold", merge=True)
    first = _manifest_object_names()
    _run_cold(merge=True)
    assert _manifest_object_names() == first


def test_aux_k170_m6_rows_order_tier2_repeat() -> None:
    """Identical tier-2 merge reruns must keep loader rows aligned with read_order.

    Fails when repeat tier-2 runs alphabetize trace rows despite stable read_order.
    """
    _clear_outputs()
    _run_cold(merge_tier=2)
    first_rows = _trace_row_objects()
    first_order = _load_trace()["read_order"]
    _run_cold(merge_tier=2)
    trace = _load_trace()
    assert _trace_row_objects() == first_rows
    assert trace["read_order"] == first_order


def test_aux_k171_m5_manifest_matches_journal_union_cold() -> None:
    """Cold manifest object name set must equal journal segment object union.

    Fails when manifest emission drops journal-listed objects or adds unstaged extras.
    """
    _rebuild("cold")
    manifest_names = set(_manifest_object_names())
    journal_names = _journal_object_names(_load_journal())
    assert manifest_names == journal_names


def test_aux_k172_m3_manifest_matches_journal_union_merge() -> None:
    """Merged manifest object set must equal journal union across both lanes.

    Fails when merge manifest omits journal-listed delta objects such as mod_disk.
    """
    _rebuild("cold", merge=True)
    manifest_names = set(_manifest_object_names())
    journal_names = _journal_object_names(_load_journal())
    assert manifest_names == journal_names


def test_aux_k173_m3_manifest_matches_journal_union_tier2() -> None:
    """Tier-2 manifest object set must equal journal union including mod_sensor.

    Fails when tier-2 manifest drops journal-listed wave_c modules from staged objects.
    """
    _rebuild("cold", merge_tier=2)
    manifest_names = set(_manifest_object_names())
    journal_names = _journal_object_names(_load_journal())
    assert manifest_names == journal_names


def test_aux_k174_m6_manifest_alpha_before_beta() -> None:
    """Cold manifest must rank fw_alpha ahead of fw_beta by descending weight.

    Fails when manifest object list preserves wave insertion order for blob-lane neighbors.
    """
    _rebuild("cold")
    names = _manifest_object_names()
    assert names.index("fw_alpha") < names.index("fw_beta")


def test_aux_k175_m8_row_read_order_chain() -> None:
    """Chained warm, cold, and merge runs must end with rows aligned to read_order.

    Fails when session reruns alphabetize loader rows after read_order is weight-correct.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0), ("cold", True, 0))
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k181_m2_warm_core_after_net() -> None:
    """Warm read_order must rank mod_net ahead of mod_core by warm weight table.

    Fails when warm loader_trace reuses cold weights where mod_core outranks mod_net.
    """
    _rebuild("warm")
    order = _load_trace()["read_order"]
    assert order.index("mod_net") < order.index("mod_core")


def test_aux_k182_m2_cold_core_before_net() -> None:
    """Cold read_order must rank mod_core ahead of mod_net by cold weight table.

    Fails when cold loader_trace reuses warm weights where mod_net outranks mod_core.
    """
    _rebuild("cold")
    order = _load_trace()["read_order"]
    assert order.index("mod_core") < order.index("mod_net")


def test_aux_k183_m6_warm_manifest_core_after_net() -> None:
    """Warm staging_manifest must list mod_net ahead of mod_core by warm weights.

    Fails when warm manifest preserves wave insertion order instead of warm weight rank.
    """
    _rebuild("warm")
    names = _manifest_object_names()
    assert names.index("mod_net") < names.index("mod_core")


def test_aux_k184_m6_cold_manifest_core_before_net() -> None:
    """Cold staging_manifest must list mod_core ahead of mod_net by cold weights.

    Fails when cold manifest sorts lexicographically or applies warm weight ranks.
    """
    _rebuild("cold")
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("mod_net")


def test_aux_k185_m2_probe_ignored_cold() -> None:
    """Host depmod probe sidecar must not force name-sorted chroot index on cold runs.

    Fails when probe_order.json overrides weight ordering in chroot_index.json.
    """
    _rebuild("cold")
    host = _load_json(APP / ".staging/host_index.json")["order"]
    chroot = _load_json(APP / ".staging/chroot_index.json")["order"]
    expected = _weight_order("cold", list(_active_wave_names()))
    assert host == expected
    assert chroot == expected


def test_aux_k186_m2_probe_ignored_warm() -> None:
    """Host depmod probe sidecar must not force name-sorted chroot index on warm runs.

    Fails when probe_order.json pins chroot order away from warm weight-table rank.
    """
    _rebuild("warm")
    host = _load_json(APP / ".staging/host_index.json")["order"]
    chroot = _load_json(APP / ".staging/chroot_index.json")["order"]
    expected = _weight_order("warm", list(_active_wave_names()))
    assert host == expected
    assert chroot == expected


def test_aux_k187_m2_probe_ignored_merge() -> None:
    """Tier-1 merge index views must ignore probe sidecar name-sort fallbacks.

    Fails when probe_order.json keeps chroot on lexical order after incremental merge.
    """
    _rebuild("cold", merge=True)
    host = _load_json(APP / ".staging/host_index.json")["order"]
    chroot = _load_json(APP / ".staging/chroot_index.json")["order"]
    expected = _weight_order("cold", list(_active_wave_names()))
    assert host == expected
    assert chroot == expected


def test_aux_k188_m2_probe_ignored_tier2() -> None:
    """Tier-2 merge index views must ignore probe sidecar name-sort fallbacks.

    Fails when probe_order.json overrides seven-object weight ordering in chroot_index.
    """
    _rebuild("cold", merge_tier=2)
    host = _load_json(APP / ".staging/host_index.json")["order"]
    chroot = _load_json(APP / ".staging/chroot_index.json")["order"]
    expected = _weight_order("cold", list(_active_wave_names()))
    assert host == expected
    assert chroot == expected


def test_aux_k189_m3_warm_stamp_sorted() -> None:
    """Warm manifest stamp must digest semicolon-joined sorted object names.

    Fails when stamp hashing uses wave insertion order instead of sorted names.
    """
    _rebuild("warm")
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("warm", names, manifest["carry"])


def test_aux_k190_m3_cold_stamp_sorted() -> None:
    """Plain cold manifest stamp must digest semicolon-joined sorted object names.

    Fails when stamp body joins unsorted wave_a insertion order with WAVE_A carry.
    """
    _rebuild("cold")
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, manifest["carry"])


def test_aux_k191_m5_warm_b_weight_order() -> None:
    """Warm B-lane journal objects must follow warm profile weight ordering.

    Fails when warm journal emission applies cold weight ranks to blob-lane rows.
    """
    _rebuild("warm")
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("warm", b_names)


def test_aux_k192_m5_warm_o_weight_order() -> None:
    """Warm O-lane journal must place mod_net ahead of mod_core by warm weights.

    Fails when warm journal preserves wave insertion order inside the object-lane row.
    """
    _rebuild("warm")
    order = _lane_objects(_load_journal(), "O")
    assert order.index("mod_net") < order.index("mod_core")


def test_aux_k193_m1_warm_beta_before_alpha() -> None:
    """Warm read_order must rank fw_beta ahead of fw_alpha by warm weight table.

    Fails when warm loader_trace applies cold blob-lane weight ranks to fw_alpha and fw_beta.
    """
    _rebuild("warm")
    order = _load_trace()["read_order"]
    assert order.index("fw_beta") < order.index("fw_alpha")


def test_aux_k194_m1_cold_alpha_before_beta() -> None:
    """Cold read_order must rank fw_alpha ahead of fw_beta by cold weight table.

    Fails when cold loader_trace reverses blob-lane neighbors with equal warm ranks.
    """
    _rebuild("cold")
    order = _load_trace()["read_order"]
    assert order.index("fw_alpha") < order.index("fw_beta")


def test_aux_k195_m6_warm_rows_match_order() -> None:
    """Warm loader trace rows must follow warm read_order sequence.

    Fails when warm trace alphabetizes rows after computing weight-sorted read_order.
    """
    _rebuild("warm")
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k196_m3_merge_stamp_sorted() -> None:
    """Tier-1 merge stamp must digest sorted six-object names with WAVE_B carry.

    Fails when merge stamp joins unsorted merged object list before hashing.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_B")


def test_aux_k197_m8_probe_then_rev_chain() -> None:
    """Warm then cold after probe sidecar write must bump rev once on stamp change.

    Fails when probe-driven carry or stamp drift suppresses epoch ledger rev updates.
    """
    _clear_outputs()
    _run_warm()
    rev_warm = _load_ledger()["rev"]
    _run_cold()
    assert _load_ledger()["rev"] == rev_warm + 1


def test_aux_k198_m2_warm_index_len() -> None:
    """Warm index order must list five active-wave objects only.

    Fails when warm rebuild includes weight-table rows outside the parent wave snapshot.
    """
    _rebuild("warm")
    host = _load_json(APP / ".staging/host_index.json")["order"]
    assert len(host) == 5
    assert set(host) == _active_wave_names()


def test_aux_k199_m6_tier2_manifest_core_before_net() -> None:
    """Tier-2 manifest must rank mod_core ahead of mod_net by cold weight table.

    Fails when tier-2 manifest applies warm ranks or wave insertion order to object-lane modules.
    """
    _rebuild("cold", merge_tier=2)
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("mod_net")


def test_aux_k200_m4_tier2_alpha_avail() -> None:
    """Tier-2 cold fw_alpha must reach avail_metric 1 on the blob-lane commit path.

    Fails when tier-2 availability logic drops B-lane required objects after wave_c staging.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    alpha = next(row for row in trace["rows"] if row["object"] == "fw_alpha")
    assert alpha["avail_metric"] == 1


def test_aux_k201_m3_warm_after_cold_carry() -> None:
    """Cold then warm in one session must restore WAVE_A carry on warm manifest.

    Fails when cold carry sidecars bleed WAVE_B into a subsequent warm profile run.
    """
    _run_sequence(("cold", True, 0), ("warm", False, 0))
    assert _load_manifest()["carry"] == "WAVE_A"


def test_aux_k202_m5_cold_o_weight_order() -> None:
    """Plain cold O-lane journal must rank mod_core ahead of mod_net by cold weights.

    Fails when object-lane journal rows preserve wave insertion order for mod_core and mod_net.
    """
    _rebuild("cold")
    order = _lane_objects(_load_journal(), "O")
    assert order.index("mod_core") < order.index("mod_net")


def test_aux_k203_m6_merge_manifest_core_before_net() -> None:
    """Tier-1 merge manifest must rank mod_core ahead of mod_net by cold weights.

    Fails when merge manifest lists mod_net ahead of mod_core despite cold weight ranks.
    """
    _rebuild("cold", merge=True)
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("mod_net")


def test_aux_k204_m2_tier2_index_probe_ignored() -> None:
    """Tier-2 host and chroot index lists must match weight order with probe sidecar present.

    Fails when probe_order.json forces lexical chroot order on seven-object tier-2 rebuilds.
    """
    _rebuild("cold", merge_tier=2)
    _index_bind_check("cold")


def test_aux_k205_m7_warm_status_dirty() -> None:
    """Warm loader status_token must be DIRTY when O-lane objects stay gated.

    Fails when warm loader emission forces CLEAN while mod_core remains at avail_metric 0.
    """
    _rebuild("warm")
    trace = _load_trace()
    metrics = {row["object"]: row["avail_metric"] for row in trace["rows"]}
    if metrics.get("mod_core", 0) == 0:
        assert trace["status_token"] == "DIRTY"


def test_aux_k206_m8_merge_then_plain_rev() -> None:
    """Plain cold after tier-1 merge must bump rev when stamp returns to parent fingerprint.

    Fails when epoch ledger ignores stamp transition from WAVE_B merge back to WAVE_A plain cold.
    """
    _clear_outputs()
    _run_cold(merge=True)
    rev_merge = _load_ledger()["rev"]
    _run_cold()
    assert _load_ledger()["rev"] == rev_merge + 1


def test_aux_k207_m1_tier2_read_core_before_net() -> None:
    """Tier-2 read_order must rank mod_core ahead of mod_net by cold weight table.

    Fails when tier-2 loader_trace applies warm weight ranks to mod_core and mod_net.
    """
    _rebuild("cold", merge_tier=2)
    order = _load_trace()["read_order"]
    assert order.index("mod_core") < order.index("mod_net")


def test_aux_k208_m5_merge_o_core_before_net() -> None:
    """Merged O-lane journal must rank mod_core ahead of mod_net by cold weights.

    Fails when merge journal keeps wave insertion order inside the object-lane segment.
    """
    _rebuild("cold", merge=True)
    order = _lane_objects(_load_journal(), "O")
    assert order.index("mod_core") < order.index("mod_net")


def test_aux_k209_m6_warm_manifest_matches_journal() -> None:
    """Warm manifest object set must equal journal segment object union.

    Fails when warm manifest emission drops journal-listed object-lane modules.
    """
    _rebuild("warm")
    manifest_names = set(_manifest_object_names())
    journal_names = _journal_object_names(_load_journal())
    assert manifest_names == journal_names


def test_aux_k210_m4_warm_rtc_not_required() -> None:
    """Warm mod_rtc must stay at avail_metric 0 because it is outside the warm required set.

    Fails when warm availability logic marks every staged object available without required membership.
    """
    _rebuild("warm")
    trace = _load_trace()
    rtc = next(row for row in trace["rows"] if row["object"] == "mod_rtc")
    assert rtc["avail_metric"] == 0


def test_aux_k211_m6_trace_profile_cold() -> None:
    """Cold loader trace profile must match staging_manifest profile.

    Fails when trace emission keeps a stale profile label from an earlier warm driver run.
    """
    _rebuild("cold")
    manifest = _load_manifest()
    trace = _load_trace()
    assert trace.get("profile") == manifest["profile"] == "cold"


def test_aux_k212_m6_trace_profile_warm() -> None:
    """Warm loader trace profile must match staging_manifest profile.

    Fails when trace emission reports cold while manifest records warm after a profile switch.
    """
    _rebuild("warm")
    manifest = _load_manifest()
    trace = _load_trace()
    assert trace.get("profile") == manifest["profile"] == "warm"


def test_aux_k213_m3_merge_wave_stage_same_profile() -> None:
    """Cold merge after plain cold must restage active_wave when profile label is unchanged.

    Fails when driver skips wave staging on merge-tier changes that reuse the same profile name.
    """
    _run_sequence(("cold", False, 0), ("cold", True, 0))
    manifest = _load_manifest()
    wave = _load_json(STAGING_WAVE)
    assert manifest["carry"] == "WAVE_B"
    assert wave["carry_token"] == "WAVE_B"
    assert len(_active_wave_names()) == 6


def test_aux_k214_m3_tier2_wave_stage_same_profile() -> None:
    """Tier-2 merge after tier-1 must restage active_wave despite cold profile reuse.

    Fails when wave staging is skipped after --merge-tier changes while --profile stays cold.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    wave = _load_json(STAGING_WAVE)
    assert wave["carry_token"] == "WAVE_C"
    assert len(_active_wave_names()) == 7


def test_aux_k215_m3_plain_tier2_wave_stage() -> None:
    """Plain cold followed by tier-2 merge must adopt seven-object wave_c snapshot.

    Fails when tier-2 invocation reuses parent active_wave because profile label never changed.
    """
    _run_sequence(("cold", False, 0), ("cold", False, 2))
    manifest = _load_manifest()
    assert manifest["carry"] == "WAVE_C"
    assert len(manifest["objects"]) == 7


def test_aux_k216_m6_trace_profile_after_warm_cold() -> None:
    """Warm-then-cold session loader trace profile must end on cold.

    Fails when trace profile sticks to warm after a subsequent cold driver invocation.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0))
    manifest = _load_manifest()
    trace = _load_trace()
    assert trace.get("profile") == manifest["profile"] == "cold"


def test_aux_k217_m3_merge_manifest_lanes() -> None:
    """Merged manifest objects must preserve active wave lane labels.

    Fails when merge manifest drops lane metadata or relabels delta modules incorrectly.
    """
    _rebuild("cold", merge=True)
    wave = _load_json(STAGING_WAVE)
    wave_lanes = {o["name"]: o["lane"] for o in wave["objects"]}
    for obj in _load_manifest()["objects"]:
        assert obj["lane"] == wave_lanes[obj["name"]]


def test_aux_k218_m3_tier2_manifest_lanes() -> None:
    """Tier-2 manifest objects must preserve active wave lane labels including mod_sensor.

    Fails when tier-2 manifest relabels wave_c object-lane modules or drops lane fields.
    """
    _rebuild("cold", merge_tier=2)
    wave = _load_json(STAGING_WAVE)
    wave_lanes = {o["name"]: o["lane"] for o in wave["objects"]}
    for obj in _load_manifest()["objects"]:
        assert obj["lane"] == wave_lanes[obj["name"]]
    sensor = next(o for o in _load_manifest()["objects"] if o["name"] == "mod_sensor")
    assert sensor["lane"] == "O"


def test_aux_k219_m6_trace_profile_merge() -> None:
    """Merged cold loader trace profile must remain cold with manifest alignment.

    Fails when merge trace reports a profile label that disagrees with staging_manifest.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    trace = _load_trace()
    assert trace.get("profile") == manifest["profile"] == "cold"


def test_aux_k220_m6_trace_profile_tier2() -> None:
    """Tier-2 cold loader trace profile must match manifest on wave_c staging.

    Fails when tier-2 trace keeps a stale profile label after merge-tier promotion.
    """
    _rebuild("cold", merge_tier=2)
    manifest = _load_manifest()
    trace = _load_trace()
    assert trace.get("profile") == manifest["profile"] == "cold"


def test_aux_k221_m3_cold_merge_then_tier2_wave() -> None:
    """Cold, tier-1 merge, and tier-2 merge must finish with mod_sensor staged.

    Fails when tier-2 wave staging is skipped because profile stayed cold across merges.
    """
    _run_sequence(("cold", False, 0), ("cold", True, 0), ("cold", False, 2))
    names = _active_wave_names()
    assert "mod_sensor" in names
    assert "mod_disk" in names
    assert len(names) == 7


def test_aux_k222_m3_merge_after_repeat_cold() -> None:
    """Second cold run followed by merge must still adopt WAVE_B six-object snapshot.

    Fails when repeat plain cold reuses profile-label staging cache and blocks merge-tier wave staging.
    """
    _run_sequence(("cold", False, 0), ("cold", False, 0), ("cold", True, 0))
    assert _load_manifest()["carry"] == "WAVE_B"
    assert len(_load_manifest()["objects"]) == 6


def test_aux_k223_m6_warm_trace_profile_repeat() -> None:
    """Two warm runs must keep loader trace profile aligned with manifest.

    Fails when repeat warm runs drift trace profile away from staging_manifest profile.
    """
    _clear_outputs()
    _run_warm()
    first = (_load_manifest()["profile"], _load_trace().get("profile"))
    _run_warm()
    second = (_load_manifest()["profile"], _load_trace().get("profile"))
    assert first == second == ("warm", "warm")


def test_aux_k224_m3_tier2_from_plain_object_count() -> None:
    """Tier-2 from plain cold must stage seven objects without requiring tier-1 first.

    Fails when tier-2 staging reuses five-object parent wave because profile never changed.
    """
    _rebuild("cold", merge_tier=2)
    assert len(_load_manifest()["objects"]) == 7
    assert "mod_disk" in _manifest_object_names()


def test_aux_k225_m6_manifest_lane_rtc_cold() -> None:
    """Plain cold manifest must keep mod_rtc on blob-lane B.

    Fails when manifest emission strips lane labels or relabels parent-wave modules.
    """
    _rebuild("cold")
    rtc = next(o for o in _load_manifest()["objects"] if o["name"] == "mod_rtc")
    assert rtc["lane"] == "B"


def test_aux_k226_m3_merge_active_wave_disk() -> None:
    """Cold merge must rewrite active_wave to include mod_disk when profile stays cold.

    Fails when merge-tier promotion is skipped because the profile label stayed cold.
    """
    _run_sequence(("cold", False, 0), ("cold", True, 0))
    wave = _load_json(STAGING_WAVE)
    assert "mod_disk" in {o["name"] for o in wave["objects"]}
    assert wave["carry_token"] == "WAVE_B"


def test_aux_k227_m6_trace_profile_warm_after_tier2() -> None:
    """Warm rebuild after tier-2 cold session must report warm on trace and manifest.

    Fails when tier-2 residue leaves cold profile on loader_trace after warm staging.
    """
    _run_sequence(("cold", False, 2), ("warm", False, 0))
    manifest = _load_manifest()
    trace = _load_trace()
    assert manifest["profile"] == "warm"
    assert trace.get("profile") == "warm"


def test_aux_k228_m3_tier2_journal_sensor_lane() -> None:
    """Tier-2 journal must list mod_sensor on O-lane after wave staging on cold profile reuse.

    Fails when skipped wave staging leaves tier-1 journal objects without mod_sensor.
    """
    _run_sequence(("cold", True, 0), ("cold", False, 2))
    o_seg = next(seg for seg in _load_journal()["segments"] if seg["lane"] == "O")
    assert "mod_sensor" in o_seg["objects"]


def test_aux_k229_m6_trace_rows_profile_parity_cold() -> None:
    """Cold trace rows and read_order must stay aligned when profile field is present.

    Fails when trace adds profile metadata but row emission still alphabetizes rows.
    """
    _rebuild("cold")
    trace = _load_trace()
    assert trace.get("profile") == "cold"
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k230_m8_rev_merge_same_profile() -> None:
    """Plain cold then merge on same profile must bump rev when stamp changes to WAVE_B.

    Fails when merge wave staging is skipped and stamp never advances from parent fingerprint.
    """
    _clear_outputs()
    _run_cold()
    rev_plain = _load_ledger()["rev"]
    _run_cold(merge=True)
    assert _load_manifest()["carry"] == "WAVE_B"
    assert _load_ledger()["rev"] == rev_plain + 1


def test_aux_k176_m3_tier2_manifest_core_first() -> None:
    """Tier-2 manifest must list mod_core ahead of mod_disk and mod_sensor by weight.

    Fails when tier-2 manifest keeps wave insertion order with mod_core after delta modules.
    """
    _rebuild("cold", merge_tier=2)
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("mod_disk")
    assert names.index("mod_core") < names.index("mod_sensor")


def test_aux_k177_m4_warm_manifest_core_first() -> None:
    """Warm manifest must list mod_core after mod_net and mod_rtc by warm weight ordering.

    Fails when warm manifest preserves wave_a insertion order with mod_core ahead of mod_net.
    """
    _rebuild("warm")
    names = _manifest_object_names()
    assert names.index("mod_net") < names.index("mod_core")
    assert names.index("mod_rtc") < names.index("mod_core")


def test_aux_k178_m6_trace_rows_len_matches_order() -> None:
    """Loader trace row count must equal read_order length on tier-2 cold rebuilds.

    Fails when row emission drops entries while read_order still lists every weight-table object.
    """
    _rebuild("cold", merge_tier=2)
    trace = _load_trace()
    assert len(trace["rows"]) == len(trace["read_order"])


def test_aux_k179_m3_merge_manifest_names_sorted() -> None:
    """Merged manifest names must match weight sort independent of wave bundle insertion order.

    Fails when merge manifest lists fw_alpha before mod_core despite cold weight ranks.
    """
    _rebuild("cold", merge=True)
    names = _manifest_object_names()
    assert names.index("mod_core") < names.index("fw_alpha")


def test_aux_k180_m8_tier2_rows_read_order_stable() -> None:
    """Tier-2 cold then plain cold must restore row sequence equal to read_order on final run.

    Fails when profile reset leaves alphabetized trace rows after tier-2 session residue.
    """
    _run_sequence(("cold", False, 2), ("cold", False, 0))
    trace = _load_trace()
    assert _trace_row_objects() == trace["read_order"]


def test_aux_k231_m9_stamp_semicolon_body() -> None:
    """Plain cold stamp must use semicolon-joined sorted names from shared stamp helpers.

    Fails when the shared stamp helper joins names with commas or skips sorting before hashing.
    """
    _rebuild("cold")
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, manifest["carry"])


def test_aux_k232_m9_stamp_sorted_names_merge() -> None:
    """Tier-1 merge stamp must match shared helper digest with WAVE_B carry.

    Fails when host bind hashes unsorted wave insertion order through the lib helper.
    """
    _rebuild("cold", merge=True)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_B")


def test_aux_k233_m9_stamp_tier2_helper() -> None:
    """Tier-2 stamp must match shared helper digest with WAVE_C carry.

    Fails when stamp helpers disagree with the published profile:names:carry body layout.
    """
    _rebuild("cold", merge_tier=2)
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("cold", names, "WAVE_C")


def test_aux_k234_m9_rank_helper_warm_journal() -> None:
    """Warm B-lane journal must follow shared weight ranking, not alphabetical sort.

    Fails when the shared ranking helper lists blob-lane names lexicographically.
    """
    _rebuild("warm")
    journal = _load_journal()
    b_names = _wave_lane_names("B")
    assert _lane_objects(journal, "B") == _lane_weight_order("warm", b_names)


def test_aux_k235_m9_rank_helper_cold_journal() -> None:
    """Cold O-lane journal must follow shared weight ranking for mod_core and mod_net.

    Fails when phase journal lane ranking uses bare name order from the shared helper.
    """
    _rebuild("cold")
    order = _lane_objects(_load_journal(), "O")
    assert order.index("mod_core") < order.index("mod_net")


def test_aux_k236_m4_cold_inherit_blob_lane() -> None:
    """Cold O-lane required objects must inherit blob-lane hook commits, not O-lane commits.

    Fails when availability uses a cold-only object-lane commit pin after hooks gate O false.
    """
    _rebuild("cold")
    trace = _load_trace()
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k237_m4_warm_inherit_blob_lane() -> None:
    """Warm O-lane required objects must inherit blob-lane hook commits on the warm path.

    Fails when warm availability still requires an object-lane commit after sched equality gating.
    """
    _rebuild("warm")
    trace = _load_trace()
    core = next(row for row in trace["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k238_m4_journal_gate_mod_core() -> None:
    """Cold mod_core avail_metric requires journal membership as well as manifest staging.

    Fails when availability ignores phase journal union and marks objects available from manifest alone.
    """
    _rebuild("cold")
    journal_names = _journal_object_names(_load_journal())
    assert "mod_core" in journal_names
    core = next(row for row in _load_trace()["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k239_m4_journal_gate_mod_disk_merge() -> None:
    """Merged mod_disk avail_metric requires journal union membership after incremental merge.

    Fails when merge stages mod_disk in the manifest but journal emission omits it from segments.
    """
    _rebuild("cold", merge=True)
    journal_names = _journal_object_names(_load_journal())
    assert "mod_disk" in journal_names
    disk = next(row for row in _load_trace()["rows"] if row["object"] == "mod_disk")
    assert disk["avail_metric"] == 1


def test_aux_k240_m4_journal_gate_mod_sensor_tier2() -> None:
    """Tier-2 mod_sensor avail_metric requires journal membership with blob-lane inherit.

    Fails when tier-2 stages mod_sensor without journaling it, leaving avail_metric at 0.
    """
    _rebuild("cold", merge_tier=2)
    journal_names = _journal_object_names(_load_journal())
    assert "mod_sensor" in journal_names
    sensor = next(row for row in _load_trace()["rows"] if row["object"] == "mod_sensor")
    assert sensor["avail_metric"] == 1


def test_aux_k241_m2_cold_hint_weight_mode() -> None:
    """Cold host and chroot indexes must stay on weight order even when worker_hint starts name-mode.

    Fails when cold profile keeps a name-sorted hint mode that drives chroot away from weight order.
    """
    _rebuild("cold")
    _index_bind_check("cold")
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    chroot = _load_json(APP / ".staging" / "chroot_index.json")["order"]
    assert host == chroot
    assert host == _weight_order("cold", list(_active_wave_names()))


def test_aux_k242_m2_warm_hint_weight_mode() -> None:
    """Warm host and chroot indexes must stay on warm weight order with weight-mode worker hints.

    Fails when warm hint mode flips back to name-sorted chroot after probe sidecar writes.
    """
    _rebuild("warm")
    _index_bind_check("warm")
    host = _load_json(APP / ".staging" / "host_index.json")["order"]
    assert host == _weight_order("warm", list(_active_wave_names()))


def test_aux_k243_m9_stamp_warm_helper() -> None:
    """Warm stamp must match shared helper digest with parent WAVE_A carry.

    Fails when warm bind hashes comma-joined or unsorted names through the lib helper.
    """
    _rebuild("warm")
    manifest = _load_manifest()
    names = [o["name"] for o in manifest["objects"]]
    assert manifest["stamp"] == _expected_stamp("warm", names, manifest["carry"])


def test_aux_k244_m4_merge_core_journal_and_inherit() -> None:
    """Merged cold mod_core must be journaled and available via blob-lane inherit together.

    Fails when merge fixes staging but leaves journal-gated availability or O-lane commit pins broken.
    """
    _rebuild("cold", merge=True)
    assert "mod_core" in _journal_object_names(_load_journal())
    core = next(row for row in _load_trace()["rows"] if row["object"] == "mod_core")
    assert core["avail_metric"] == 1


def test_aux_k245_m9_rank_rtc_before_beta() -> None:
    """Cold B-lane journal must rank mod_rtc ahead of fw_beta through the shared weight helper.

    Fails when the shared ranking helper alphabetizes fw_beta ahead of mod_rtc inside the blob-lane segment.
    """
    _rebuild("cold")
    order = _lane_objects(_load_journal(), "B")
    assert order.index("mod_rtc") < order.index("fw_beta")


def test_aux_k246_m8_stamp_change_bumps_rev() -> None:
    """Plain cold then merge must bump epoch ledger rev when shared stamp helper changes the digest.

    Fails when stamp helpers keep a wrong body layout so consecutive stamps collide and rev stays flat.
    """
    _clear_outputs()
    _run_cold()
    rev_plain = _load_ledger()["rev"]
    stamp_plain = _load_manifest()["stamp"]
    _run_cold(merge=True)
    assert _load_manifest()["stamp"] != stamp_plain
    assert _load_ledger()["rev"] == rev_plain + 1


def test_aux_k247_m4_cold_disk_absent_journal_gate() -> None:
    """Plain cold must keep mod_disk at avail_metric 0 when it is absent from journal and manifest.

    Fails when availability marks weight-table objects available without journal membership.
    """
    _rebuild("cold")
    assert "mod_disk" not in _journal_object_names(_load_journal())
    metrics = {row["object"]: row["avail_metric"] for row in _load_trace()["rows"]}
    assert metrics.get("mod_disk") == 0


def test_aux_k248_m2_session_warm_cold_indexes() -> None:
    """Warm then cold session must end with cold weight-ordered host and chroot indexes.

    Fails when warm weight-mode hints leave cold on a stale name-sorted chroot order.
    """
    _run_sequence(("warm", False, 0), ("cold", False, 0))
    _index_bind_check("cold")


def test_aux_k249_m9_tier2_journal_rank_helper() -> None:
    """Tier-2 O-lane journal must weight-rank mod_sensor after heavier object-lane modules.

    Fails when the shared ranking helper alphabetizes mod_sensor ahead of mod_core.
    """
    _rebuild("cold", merge_tier=2)
    order = _lane_objects(_load_journal(), "O")
    assert order.index("mod_core") < order.index("mod_sensor")
    assert order.index("mod_disk") < order.index("mod_sensor")


def test_aux_k250_m4_parity_matches_journal_gate_warm() -> None:
    """Warm required-object avail metrics must match journal-gated hook parity expectations.

    Fails when warm inherit or journal gating diverges from the published availability rules.
    """
    _rebuild("warm")
    trace = _load_trace()
    parity = _parity("warm")
    parity_by_object = {row["object"]: row for row in parity["rows"]}
    for name in PROFILES["profiles"]["warm"]["required"]:
        row = next(r for r in trace["rows"] if r["object"] == name)
        assert row["avail_metric"] == parity_by_object[name]["avail_metric"]
