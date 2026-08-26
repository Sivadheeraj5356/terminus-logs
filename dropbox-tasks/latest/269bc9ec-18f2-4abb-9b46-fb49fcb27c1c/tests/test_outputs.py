import hashlib
import json
import math
import os
import struct
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


APP = Path("/app")
REPORT = APP / "output/parity-report.json"
MODEL_DIR = APP / "models/mobilenet-v3-parity"
EXPECTED_ARTIFACTS = [
    "mobilenet_v3_large.pt",
    "mobilenet_v3_large.onnx",
    "mobilenet_v3_large.onnx.data",
    "config.json",
]
EXPECTED_PYTORCH_BASELINES = {
    "warm-gradient": ([4, 12, 22, 24, 18], 0.55267833),
    "cool-checker": ([12, 4, 25, 18, 32], 0.63192716),
    "neutral-rings": ([4, 12, 16, 25, 22], 0.55761437),
}


def read_json(path: Path) -> dict:
    """Read a UTF-8 JSON object from a verifier-visible path."""
    return json.loads(path.read_text(encoding="utf-8"))


def run_trial(
    manifest: Path,
    policy: Path,
    output: Path,
    model_dir: Path = MODEL_DIR,
    source: Path = APP / "config/model-source.properties",
) -> subprocess.CompletedProcess[str]:
    """Run the trial wrapper with explicit input and output paths."""
    environment = os.environ.copy()
    environment.update(
        {
            "MANIFEST": str(manifest),
            "POLICY": str(policy),
            "OUTPUT": str(output),
            "MODEL_DIR": str(model_dir),
            "MODEL_SOURCE_CONFIG": str(source),
        }
    )
    return subprocess.run(
        ["/app/scripts/run_trial.sh"],
        cwd=APP,
        env=environment,
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )


def run_java(arguments: list[str]) -> subprocess.CompletedProcess[str]:
    """Invoke the evaluator CLI directly with a caller-provided argument list."""
    return subprocess.run(
        [
            "java",
            "-Dai.djl.offline=true",
            "-cp",
            "/app/target/djl-parity-trial-1.0.0.jar:/app/target/dependency/*",
            "org.example.parity.Main",
            *arguments,
        ],
        cwd=APP,
        text=True,
        capture_output=True,
        timeout=30,
        check=False,
    )


def assert_transactional_failure(
    completed: subprocess.CompletedProcess[str], output: Path, expected: bytes
) -> None:
    """Assert failure leaves a protected output unchanged and emits no stdout."""
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert completed.stderr.strip()
    assert output.read_bytes() == expected


def top_indices(probabilities: list[float], count: int) -> list[int]:
    """Return descending probability indices with lower-index tie breaking."""
    return sorted(range(len(probabilities)), key=lambda index: (-probabilities[index], index))[:count]


def make_ppm(path: Path, width: int, height: int, seed: int, maximum: int = 31) -> None:
    """Create a deterministic ASCII P3 image that was not shipped with the task."""
    samples = []
    for y_coord in range(height):
        for x_coord in range(width):
            samples.extend(
                [
                    (x_coord * 7 + y_coord * 3 + seed) % (maximum + 1),
                    (x_coord * 2 + y_coord * 11 + seed * 3) % (maximum + 1),
                    (x_coord * 13 + y_coord * 5 + seed * 7) % (maximum + 1),
                ]
            )
    rows = ["P3", "# verifier-created rectangular image", f"{width} {height}", str(maximum)]
    rows.extend(" ".join(map(str, samples[index : index + 18])) for index in range(0, len(samples), 18))
    path.write_text("\n".join(rows) + "\n", encoding="ascii")


def manifest_record(identifier: str, image: Path, relative: str, group: str = "runtime") -> str:
    """Build one compact manifest record bound to the current image digest."""
    return json.dumps(
        {
            "id": identifier,
            "image": relative,
            "sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
            "group": group,
        },
        separators=(",", ":"),
    )


def policy_text(batch_sizes: list[int], groups: list[str] | None = None, top_k: int = 2) -> str:
    """Build a compact valid policy for runtime-created verifier inputs."""
    groups = groups or ["runtime"]
    return json.dumps(
        {
            "top_k": top_k,
            "max_probability_drift": 0.1,
            "max_batch_drift": 0.1,
            "max_js_divergence": 0.1,
            "batch_sizes": batch_sizes,
            "required_groups": groups,
        },
        separators=(",", ":"),
    ) + "\n"


def half_up(value: float) -> float:
    """Round a finite report value to the contract's eight decimal places."""
    return float(Decimal(str(value)).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP))


def js_divergence(left: list[float], right: list[float]) -> float:
    """Calculate base-2 Jensen-Shannon divergence for two probability vectors."""
    total = 0.0
    for a_value, b_value in zip(left, right, strict=True):
        midpoint = (a_value + b_value) / 2
        if a_value > 0:
            total += 0.5 * a_value * math.log2(a_value / midpoint)
        if b_value > 0:
            total += 0.5 * b_value * math.log2(b_value / midpoint)
    return max(0.0, total)


def expected_tensor_sha256(width: int, height: int, seed: int, maximum: int = 31) -> str:
    """Independently derive the expected shared-tensor fingerprint for a generated image."""
    short = min(width, height)
    resized_width = (2 * width * 256 + short - 1) // (2 * short)
    resized_height = (2 * height * 256 + short - 1) // (2 * short)
    means = [0.485, 0.456, 0.406]
    stds = [0.229, 0.224, 0.225]
    offset_x = (resized_width - 224) // 2
    offset_y = (resized_height - 224) // 2

    def pixel(x_coord: int, y_coord: int, channel: int) -> float:
        formulas = (
            x_coord * 7 + y_coord * 3 + seed,
            x_coord * 2 + y_coord * 11 + seed * 3,
            x_coord * 13 + y_coord * 5 + seed * 7,
        )
        return formulas[channel] % (maximum + 1) / maximum

    digest = hashlib.sha256()
    for channel in range(3):
        for y_coord in range(224):
            destination_y = y_coord + offset_y
            source_y = (destination_y + 0.5) * height / resized_height - 0.5
            floor_y = math.floor(source_y)
            y0 = min(max(floor_y, 0), height - 1)
            y1 = min(max(y0 + 1, 0), height - 1)
            wy = min(max(source_y - floor_y, 0.0), 1.0)
            for x_coord in range(224):
                destination_x = x_coord + offset_x
                source_x = (destination_x + 0.5) * width / resized_width - 0.5
                floor_x = math.floor(source_x)
                x0 = min(max(floor_x, 0), width - 1)
                x1 = min(max(x0 + 1, 0), width - 1)
                wx = min(max(source_x - floor_x, 0.0), 1.0)
                top = pixel(x0, y0, channel) * (1 - wx) + pixel(x1, y0, channel) * wx
                bottom = pixel(x0, y1, channel) * (1 - wx) + pixel(x1, y1, channel) * wx
                resized = top * (1 - wy) + bottom * wy
                value = (resized - means[channel]) / stds[channel]
                digest.update(struct.pack("<f", value))
    return digest.hexdigest()


def test_model_provenance_and_baseline_report_contract() -> None:
    """The published report proves the pinned paired artifacts and complete result schema."""
    assert REPORT.is_file()
    assert REPORT.read_bytes().endswith(b"\n")
    report = read_json(REPORT)
    assert list(report) == ["schema_version", "model", "preprocessing", "policy", "samples", "summary"]
    assert report["schema_version"] == 2
    assert report["model"]["repository"] == "ihoflaz/dibas-mobilenet-v3-large"
    assert report["model"]["revision"] == "42afed175c09a6b860fd7071283c3f9621ff4cd3"
    artifacts = report["model"]["artifacts"]
    assert list(report["model"]) == ["repository", "revision", "artifacts"]
    assert [item["file"] for item in artifacts] == EXPECTED_ARTIFACTS
    for item in artifacts:
        assert list(item) == ["file", "sha256"]
        digest = hashlib.sha256((MODEL_DIR / item["file"]).read_bytes()).hexdigest()
        assert item["sha256"] == digest
    assert report["preprocessing"] == {
        "resize_shorter": 256,
        "crop_size": 224,
        "layout": "NCHW",
        "channel_order": "RGB",
        "scale": "1/max_value",
        "mean": [0.485, 0.456, 0.406],
        "std": [0.229, 0.224, 0.225],
        "tensor_fingerprint": "sha256-f32le-nchw",
    }
    assert report["summary"]["sample_count"] == 3
    assert list(report["summary"]) == [
        "sample_count",
        "group_results",
        "all_batch_sizes_supported",
        "all_top_k_match",
        "max_probability_drift",
        "max_js_divergence",
        "max_batch_drift",
        "portability_gate",
    ]


def test_probabilities_rankings_and_cross_engine_parity() -> None:
    """Real engine outputs form normalized vectors and stable label-index rankings."""
    report = read_json(REPORT)
    labels_by_id = read_json(MODEL_DIR / "config.json")["id2label"]
    labels = [labels_by_id[str(index)] for index in range(len(labels_by_id))]
    assert [sample["id"] for sample in report["samples"]] == [
        "warm-gradient",
        "cool-checker",
        "neutral-rings",
    ]
    vectors = []
    for sample in report["samples"]:
        assert list(sample) == [
            "id", "image", "sha256", "group", "tensor_sha256", "engines", "profiles", "gate_pass"
        ]
        assert sample["sha256"] == hashlib.sha256((APP / "input" / sample["image"]).read_bytes()).hexdigest()
        assert len(sample["tensor_sha256"]) == 64
        for engine_name in ["pytorch", "onnxruntime"]:
            engine = sample["engines"][engine_name]
            assert list(engine) == ["probabilities", "top_k"]
            probabilities = engine["probabilities"]
            assert len(probabilities) == 33
            assert all(math.isfinite(value) and 0 <= value <= 1 for value in probabilities)
            assert math.isclose(sum(probabilities), 1.0, abs_tol=2e-7)
            expected_indices = top_indices(probabilities, report["policy"]["top_k"])
            assert [item["index"] for item in engine["top_k"]] == expected_indices
            assert all(list(item) == ["index", "label", "probability"] for item in engine["top_k"])
            assert [item["label"] for item in engine["top_k"]] == [labels[index] for index in expected_indices]
        left = sample["engines"]["pytorch"]["probabilities"]
        right = sample["engines"]["onnxruntime"]["probabilities"]
        expected_ranking, expected_winner_probability = EXPECTED_PYTORCH_BASELINES[sample["id"]]
        assert [item["index"] for item in sample["engines"]["pytorch"]["top_k"]] == expected_ranking
        assert math.isclose(
            left[expected_ranking[0]], expected_winner_probability, abs_tol=3e-5
        )
        baseline_profile = sample["profiles"][0]
        assert baseline_profile["pytorch_probabilities"] == left
        assert baseline_profile["onnxruntime_probabilities"] == right
        assert baseline_profile["cross_engine_max_drift"] == round(
            max(abs(a_value - b_value) for a_value, b_value in zip(left, right, strict=True)), 8
        )
        assert baseline_profile["cross_engine_js_divergence"] == half_up(js_divergence(left, right))
        vectors.append(tuple(left))
    assert len(set(vectors)) == 3


def test_profile_rankings_are_plain_integer_index_lists() -> None:
    """Profile rankings use index arrays, distinct from detailed engine-level top-k objects."""
    report = read_json(REPORT)
    top_k = report["policy"]["top_k"]
    for sample in report["samples"]:
        for profile in sample["profiles"]:
            if profile["pytorch_batch_supported"]:
                probabilities = profile["pytorch_probabilities"]
                assert profile["pytorch_top_k"] == top_indices(probabilities, top_k)
                assert all(type(index) is int for index in profile["pytorch_top_k"])
            else:
                assert profile["pytorch_top_k"] is None
            if profile["onnxruntime_batch_supported"]:
                probabilities = profile["onnxruntime_probabilities"]
                assert profile["onnxruntime_top_k"] == top_indices(probabilities, top_k)
                assert all(type(index) is int for index in profile["onnxruntime_top_k"])
            else:
                assert profile["onnxruntime_top_k"] is None


def test_batch_support_is_reported_as_a_gate_result() -> None:
    """Requested native batch profiles are measured and unsupported exports fail the gate."""
    report = read_json(REPORT)
    assert report["policy"]["batch_sizes"] == [1, 2, 3]
    for sample in report["samples"]:
        assert [profile["batch_size"] for profile in sample["profiles"]] == [1, 2, 3]
        first, second, third = sample["profiles"]
        assert first["pytorch_batch_supported"] is True
        assert first["onnxruntime_batch_supported"] is True
        assert first["top_k_match"] is True
        for profile in [second, third]:
            assert list(profile) == [
                "batch_size",
                "pytorch_batch_supported",
                "onnxruntime_batch_supported",
                "pytorch_probabilities",
                "onnxruntime_probabilities",
                "cross_engine_max_drift",
                "cross_engine_js_divergence",
                "pytorch_batch_max_drift",
                "onnxruntime_batch_max_drift",
                "pytorch_top_k",
                "onnxruntime_top_k",
                "top_k_match",
            ]
            assert profile["pytorch_batch_supported"] is True
            assert profile["onnxruntime_batch_supported"] is False
            assert profile["cross_engine_max_drift"] is None
            assert profile["onnxruntime_probabilities"] is None
            assert profile["onnxruntime_batch_max_drift"] is None
            assert profile["onnxruntime_top_k"] is None
            assert profile["top_k_match"] is False
        assert sample["gate_pass"] is False
    summary = report["summary"]
    assert summary["all_batch_sizes_supported"] is False
    assert summary["portability_gate"] is False
    assert 0 <= summary["max_probability_drift"] <= report["policy"]["max_probability_drift"]
    assert [group["group"] for group in summary["group_results"]] == [
        "color-controls", "texture-controls"
    ]
    assert [group["sample_count"] for group in summary["group_results"]] == [1, 2]
    assert all(group["gate_pass"] is False for group in summary["group_results"])


def test_fresh_images_are_evaluated_in_manifest_order(tmp_path: Path) -> None:
    """Runtime-created images use real inference in manifest order without fixture hardcoding."""
    image_dir = tmp_path / "fresh"
    image_dir.mkdir()
    specs = [("wide", 11, 5, 2), ("tall", 5, 13, 9), ("square", 7, 7, 15)]
    manifest_lines = []
    for identifier, width, height, seed in specs:
        image = image_dir / f"{identifier}.ppm"
        make_ppm(image, width, height, seed)
        group = "shapes-a" if identifier != "square" else "shapes-b"
        manifest_lines.append(manifest_record(identifier, image, f"fresh/{identifier}.ppm", group))
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(policy_text([1, 3], ["shapes-a", "shapes-b"], top_k=3), encoding="utf-8")
    output = tmp_path / "fresh-report.json"
    sibling = tmp_path / "fresh-report.json.tmp"
    sibling.write_bytes(b"do-not-touch\n")
    completed = run_trial(manifest, policy, output)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout == ""
    report = read_json(output)
    assert [sample["id"] for sample in report["samples"]] == [item[0] for item in specs]
    assert [sample["image"] for sample in report["samples"]] == [
        "fresh/wide.ppm",
        "fresh/tall.ppm",
        "fresh/square.ppm",
    ]
    assert report["summary"]["sample_count"] == 3
    assert [group["group"] for group in report["summary"]["group_results"]] == ["shapes-a", "shapes-b"]
    assert len({tuple(sample["engines"]["pytorch"]["probabilities"]) for sample in report["samples"]}) == 3
    assert sibling.read_bytes() == b"do-not-touch\n"
    assert not list(tmp_path.glob(".fresh-report.json.*.tmp"))


def test_rectangular_tensor_fingerprint_uses_half_down_resize(tmp_path: Path) -> None:
    """An exact-half rectangular resize chooses the lower dimension before fingerprinting."""
    image = tmp_path / "half-tie.ppm"
    make_ppm(image, 513, 512, 6, maximum=7)
    manifest = tmp_path / "half-tie-manifest.jsonl"
    manifest.write_text(
        manifest_record("half-tie", image, "half-tie.ppm") + "\n",
        encoding="utf-8",
    )
    policy = tmp_path / "half-tie-policy.json"
    policy.write_text(policy_text([1], top_k=3), encoding="utf-8")
    output = tmp_path / "half-tie-report.json"
    completed = run_trial(manifest, policy, output)
    assert completed.returncode == 0, completed.stderr
    report = read_json(output)
    assert report["samples"][0]["tensor_sha256"] == expected_tensor_sha256(
        513, 512, 6, maximum=7
    )


def test_invalid_input_preserves_output_and_unrelated_tmp_file(tmp_path: Path) -> None:
    """Duplicate manifest IDs fail nonzero while preserving the report and unrelated sibling temp file."""
    image = tmp_path / "image.ppm"
    make_ppm(image, 3, 4, 1)
    manifest = tmp_path / "manifest.jsonl"
    line = manifest_record("duplicate", image, "image.ppm")
    manifest.write_text(f"{line}\n{line}\n", encoding="utf-8")
    policy = tmp_path / "policy.json"
    policy.write_text(policy_text([1, 2]), encoding="utf-8")
    output = tmp_path / "protected.json"
    sentinel = b"existing-report\n"
    output.write_bytes(sentinel)
    sibling = tmp_path / "protected.json.tmp"
    sibling.write_bytes(b"unrelated\n")
    completed = run_trial(manifest, policy, output)
    assert_transactional_failure(completed, output, sentinel)
    assert sibling.read_bytes() == b"unrelated\n"


def test_additional_invalid_contract_inputs_fail_transactionally(tmp_path: Path) -> None:
    """Unsafe paths, extra PPM pixels, duplicate batches, and corrupt model metadata all fail safely."""
    valid_image = tmp_path / "valid.ppm"
    make_ppm(valid_image, 4, 3, 4)
    valid_manifest = tmp_path / "valid.jsonl"
    valid_manifest.write_text(manifest_record("valid", valid_image, "valid.ppm") + "\n", encoding="utf-8")
    valid_policy = tmp_path / "valid-policy.json"
    valid_policy.write_text(policy_text([1]), encoding="utf-8")

    unsafe_manifest = tmp_path / "unsafe.jsonl"
    unsafe_manifest.write_text(
        json.dumps({"id":"unsafe","image":"../outside.ppm","sha256":"0" * 64,"group":"runtime"}, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )

    malformed_image = tmp_path / "malformed.ppm"
    malformed_image.write_text("P3\n1 1\n255\n0 0 0 9\n", encoding="ascii")
    malformed_manifest = tmp_path / "malformed.jsonl"
    malformed_manifest.write_text(
        manifest_record("malformed", malformed_image, "malformed.ppm") + "\n", encoding="utf-8"
    )

    duplicate_policy = tmp_path / "duplicate-policy.json"
    duplicate_policy.write_text(policy_text([1, 1]), encoding="utf-8")

    corrupt_model_dir = tmp_path / "corrupt-model"
    corrupt_model_dir.mkdir()
    for filename in EXPECTED_ARTIFACTS[:-1]:
        os.link(MODEL_DIR / filename, corrupt_model_dir / filename)
    (corrupt_model_dir / "config.json").write_text("{}\n", encoding="utf-8")

    cases = [
        (unsafe_manifest, valid_policy, MODEL_DIR),
        (malformed_manifest, valid_policy, MODEL_DIR),
        (valid_manifest, duplicate_policy, MODEL_DIR),
        (valid_manifest, valid_policy, corrupt_model_dir),
    ]
    for index, (manifest, policy, model_dir) in enumerate(cases):
        output = tmp_path / f"protected-{index}.json"
        output.write_bytes(b"keep-me\n")
        completed = run_trial(manifest, policy, output, model_dir)
        assert_transactional_failure(completed, output, b"keep-me\n")


def test_cli_surface_rejects_unknown_duplicate_and_relative_options(tmp_path: Path) -> None:
    """Every CLI path option is absolute and appears exactly once; invalid invocations remain transactional."""
    output = tmp_path / "cli-protected.json"
    sentinel = b"cli-sentinel\n"
    valid = [
        "--manifest", "/app/input/manifest.jsonl",
        "--policy", "/app/config/parity-policy.json",
        "--model-dir", str(MODEL_DIR),
        "--source", "/app/config/model-source.properties",
        "--output", str(output),
    ]
    cases = [
        valid[:-2] + ["--mystery", str(output)],
        valid[:-2] + ["--manifest", str(output)],
        valid[:1] + ["input/manifest.jsonl"] + valid[2:],
        valid[:1] + ["/app/input/../input/manifest.jsonl"] + valid[2:],
        valid[:-1],
    ]
    for arguments in cases:
        output.write_bytes(sentinel)
        assert_transactional_failure(run_java(arguments), output, sentinel)


def test_source_properties_are_strict_and_artifacts_are_digest_verified(tmp_path: Path) -> None:
    """Malformed provenance files and checksum-mismatched artifacts fail before inference without output damage."""
    output = tmp_path / "source-protected.json"
    sentinel = b"source-sentinel\n"
    output.write_bytes(sentinel)
    malformed_source = tmp_path / "source.properties"
    malformed_source.write_text(
        "repository=ihoflaz/dibas-mobilenet-v3-large\n"
        "revision=NOT-A-REVISION\n",
        encoding="utf-8",
    )
    completed = run_trial(
        APP / "input/manifest.jsonl",
        APP / "config/parity-policy.json",
        output,
        source=malformed_source,
    )
    assert_transactional_failure(completed, output, sentinel)

    reordered_source = tmp_path / "reordered.properties"
    source_lines = (APP / "config/model-source.properties").read_text(encoding="utf-8").splitlines()
    reordered_source.write_text("\n".join([source_lines[1], source_lines[0], *source_lines[2:]]) + "\n")
    completed = run_trial(
        APP / "input/manifest.jsonl",
        APP / "config/parity-policy.json",
        output,
        source=reordered_source,
    )
    assert_transactional_failure(completed, output, sentinel)

    corrupt_model = tmp_path / "corrupt-model"
    corrupt_model.mkdir()
    for filename in EXPECTED_ARTIFACTS:
        os.link(MODEL_DIR / filename, corrupt_model / filename)
    (corrupt_model / "mobilenet_v3_large.pt").unlink()
    (corrupt_model / "mobilenet_v3_large.pt").write_bytes(b"wrong weights")
    completed = run_trial(
        APP / "input/manifest.jsonl",
        APP / "config/parity-policy.json",
        output,
        model_dir=corrupt_model,
    )
    assert_transactional_failure(completed, output, sentinel)


def test_label_metadata_requires_consecutive_unique_nonempty_classes(tmp_path: Path) -> None:
    """Checksum-valid model metadata still fails when class indices or label values violate the contract."""
    for index, mapping in enumerate(
        [
            {"0": "same", "1": "same"},
            {"0": "first", "2": "gap"},
            {"0": ""},
            {"1": "second", "0": "first"},
        ]
    ):
        model_dir = tmp_path / f"labels-model-{index}"
        model_dir.mkdir()
        for filename in EXPECTED_ARTIFACTS[:-1]:
            os.link(MODEL_DIR / filename, model_dir / filename)
        (model_dir / "config.json").write_text(
            json.dumps({"id2label": mapping}) + "\n", encoding="utf-8"
        )
        source = tmp_path / f"labels-source-{index}.properties"
        lines = [
            "repository=ihoflaz/dibas-mobilenet-v3-large",
            "revision=42afed175c09a6b860fd7071283c3f9621ff4cd3",
        ]
        for filename in EXPECTED_ARTIFACTS:
            digest = hashlib.sha256((model_dir / filename).read_bytes()).hexdigest()
            lines.append(f"{filename}={digest}")
        source.write_text("\n".join(lines) + "\n", encoding="utf-8")
        output = tmp_path / f"labels-protected-{index}.json"
        output.write_bytes(b"labels-sentinel\n")
        assert_transactional_failure(
            run_trial(
                APP / "input/manifest.jsonl",
                APP / "config/parity-policy.json",
                output,
                model_dir=model_dir,
                source=source,
            ),
            output,
            b"labels-sentinel\n",
        )


def test_symlinked_trust_boundaries_and_output_components_are_rejected(tmp_path: Path) -> None:
    """Manifest, source, model, and output symlinks cannot cross the trial trust boundary."""
    output = tmp_path / "protected.json"
    output.write_bytes(b"trust-sentinel\n")
    linked_manifest = tmp_path / "linked-manifest.jsonl"
    linked_manifest.symlink_to(APP / "input/manifest.jsonl")
    assert_transactional_failure(
        run_trial(linked_manifest, APP / "config/parity-policy.json", output),
        output,
        b"trust-sentinel\n",
    )

    linked_source = tmp_path / "linked-source.properties"
    linked_source.symlink_to(APP / "config/model-source.properties")
    assert_transactional_failure(
        run_trial(APP / "input/manifest.jsonl", APP / "config/parity-policy.json", output, source=linked_source),
        output,
        b"trust-sentinel\n",
    )

    linked_model = tmp_path / "linked-model"
    linked_model.symlink_to(MODEL_DIR, target_is_directory=True)
    assert_transactional_failure(
        run_trial(APP / "input/manifest.jsonl", APP / "config/parity-policy.json", output, model_dir=linked_model),
        output,
        b"trust-sentinel\n",
    )

    real_output_dir = tmp_path / "real-output"
    real_output_dir.mkdir()
    target_output = real_output_dir / "report.json"
    target_output.write_bytes(b"linked-target\n")
    linked_output_dir = tmp_path / "linked-output"
    linked_output_dir.symlink_to(real_output_dir, target_is_directory=True)
    completed = run_trial(
        APP / "input/manifest.jsonl",
        APP / "config/parity-policy.json",
        linked_output_dir / "report.json",
    )
    assert completed.returncode != 0
    assert completed.stdout == ""
    assert target_output.read_bytes() == b"linked-target\n"
def test_manifest_shape_blank_lines_and_symlink_components_are_rejected(tmp_path: Path) -> None:
    """Strict JSONL key order, nonblank records, and symlink-free containment are enforced transactionally."""
    image = tmp_path / "image.ppm"
    make_ppm(image, 2, 2, 3)
    linked = tmp_path / "linked"
    linked.symlink_to(tmp_path, target_is_directory=True)
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    manifests: list[str | bytes] = [
        '{"image":"image.ppm","id":"wrong-order"}\n',
        '{"id":"extra","image":"image.ppm","note":true}\n',
        manifest_record("blank", image, "image.ppm") + "\n\n",
        json.dumps({"id":"linked","image":"linked/image.ppm","sha256":digest,"group":"runtime"}, separators=(",", ":")) + "\n",
        b'\xef\xbb\xbf{"id":"bom","image":"image.ppm","sha256":"' + digest.encode() + b'","group":"runtime"}\n',
        '{"id":"duplicate-key","image":"image.ppm","sha256":"' + digest + '","group":"runtime","group":"runtime"}\n',
        '{"id":"wrong-digest","image":"image.ppm","sha256":"' + "0" * 64 + '","group":"runtime"}\n',
    ]
    policy = tmp_path / "policy.json"
    policy.write_text(policy_text([1]), encoding="utf-8")
    for index, body in enumerate(manifests):
        manifest = tmp_path / f"manifest-{index}.jsonl"
        if isinstance(body, bytes):
            manifest.write_bytes(body)
        else:
            manifest.write_text(body, encoding="utf-8")
        output = tmp_path / f"manifest-protected-{index}.json"
        output.write_bytes(b"manifest-sentinel\n")
        assert_transactional_failure(
            run_trial(manifest, policy, output), output, b"manifest-sentinel\n"
        )


def test_policy_types_ranges_key_order_and_batch_bounds_are_rejected(tmp_path: Path) -> None:
    """Policy parsing rejects reordered keys, nonfinite/type-invalid limits, and unsupported batch profiles."""
    image = tmp_path / "image.ppm"
    make_ppm(image, 2, 2, 5)
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text(manifest_record("one", image, "image.ppm") + "\n", encoding="utf-8")
    policies = [
        '{"batch_sizes":[1],"top_k":2,"max_probability_drift":0.1,"max_batch_drift":0.1}',
        '{"top_k":2.0,"max_probability_drift":0.1,"max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1],"required_groups":["runtime"]}',
        '{"top_k":2,"max_probability_drift":"0.1","max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1],"required_groups":["runtime"]}',
        '{"top_k":2,"max_probability_drift":1.1,"max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1],"required_groups":["runtime"]}',
        '{"top_k":2,"max_probability_drift":0.1,"max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1,2],"required_groups":["runtime"]}',
        '{"top_k":2,"max_probability_drift":0.1,"max_batch_drift":0.1,"max_js_divergence":1.1,"batch_sizes":[1],"required_groups":["runtime"]}',
        '{"top_k":2,"max_probability_drift":0.1,"max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1],"required_groups":["missing"]}',
        '{"top_k":2,"max_probability_drift":0.1,"max_batch_drift":0.1,"max_js_divergence":0.1,"batch_sizes":[1],"required_groups":["runtime","runtime"]}',
    ]
    for index, body in enumerate(policies):
        policy = tmp_path / f"policy-{index}.json"
        policy.write_text(body + "\n", encoding="utf-8")
        output = tmp_path / f"policy-protected-{index}.json"
        output.write_bytes(b"policy-sentinel\n")
        assert_transactional_failure(
            run_trial(manifest, policy, output), output, b"policy-sentinel\n"
        )


def test_ppm_decoder_rejects_non_ascii_bad_ranges_and_wrong_sample_counts(tmp_path: Path) -> None:
    """The P3 decoder rejects non-ASCII data, invalid dimensions/ranges, and incomplete rasters safely."""
    policy = tmp_path / "policy.json"
    policy.write_text(policy_text([1]), encoding="utf-8")
    images = [
        b"P3\n1 1\n255\n0 0 \xff\n",
        b"P3\n0 1\n255\n",
        b"P3\n1 1\n0\n0 0 0\n",
        b"P3\n1 1\n255\n0 0\n",
        b"P3\n1 1\n255\n0 0 256\n",
    ]
    for index, content in enumerate(images):
        image = tmp_path / f"bad-{index}.ppm"
        image.write_bytes(content)
        manifest = tmp_path / f"ppm-manifest-{index}.jsonl"
        manifest.write_text(
            manifest_record(f"bad-{index}", image, image.name) + "\n",
            encoding="utf-8",
        )
        output = tmp_path / f"ppm-protected-{index}.json"
        output.write_bytes(b"ppm-sentinel\n")
        assert_transactional_failure(
            run_trial(manifest, policy, output), output, b"ppm-sentinel\n"
        )
