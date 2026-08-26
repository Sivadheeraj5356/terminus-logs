"""Milestone 1 verifiers for deterministic ImageMagick feature extraction."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path


FIXTURES = Path("/app/fixtures/images")
EXTRACTOR = Path("/app/lib/image_feature_extractor.rb")


def _ruby(code: str) -> str:
    proc = subprocess.run(
        ["bundle", "exec", "ruby", "-e", code],
        cwd="/app",
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert proc.returncode == 0, f"ruby failed:\n{proc.stderr}\n{proc.stdout}"
    return proc.stdout.strip()


class TestMilestone1:
    """Deterministic ImageMagick feature extraction and serialization."""

    def test_extract_runs_successfully(self) -> None:
        """ImageFeatureExtractor.extract must run without NotImplementedError on a fixture image."""
        image = sorted(FIXTURES.glob("*.png"))[0]
        proc = subprocess.run(
            [
                "bundle",
                "exec",
                "ruby",
                "-e",
                f"require_relative '/app/config/boot'; f = ImageFeatureExtractor.extract('{image}'); puts f[:checksum]",
            ],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert len(proc.stdout.strip()) >= 32

    def test_scripted_feature_suite_passes(self) -> None:
        """`bundle exec ruby /app/scripts/test_features.rb` must exit successfully."""
        proc = subprocess.run(
            ["bundle", "exec", "ruby", "/app/scripts/test_features.rb"],
            cwd="/app",
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr + proc.stdout
        assert "OK" in proc.stdout

    def test_extract_returns_required_fields(self) -> None:
        """extract() returns width, height, mean_rgb (3 ints), and checksum string."""
        image = sorted(FIXTURES.glob("*.png"))[0]
        out = _ruby(
            f"""
require_relative '/app/config/boot'
f = ImageFeatureExtractor.extract('{image}')
puts JSON.generate({{
  'width' => f[:width],
  'height' => f[:height],
  'mean_rgb' => f[:mean_rgb],
  'checksum' => f[:checksum],
  'keys' => f.keys.map(&:to_s).sort
}})
"""
        )
        data = json.loads(out)
        assert data["width"] == 224
        assert data["height"] == 224
        assert isinstance(data["mean_rgb"], list) and len(data["mean_rgb"]) == 3
        assert all(isinstance(x, int) for x in data["mean_rgb"])
        assert isinstance(data["checksum"], str) and len(data["checksum"]) >= 32

    def test_checksum_stable_across_calls(self) -> None:
        """Two extracts of the same fixture image must yield identical checksums."""
        image = sorted(FIXTURES.glob("*.png"))[0]
        out = _ruby(
            f"""
require_relative '/app/config/boot'
a = ImageFeatureExtractor.extract('{image}')
b = ImageFeatureExtractor.extract('{image}')
puts JSON.generate({{'a' => a[:checksum], 'b' => b[:checksum], 'eq' => a == b}})
"""
        )
        data = json.loads(out)
        assert data["a"] == data["b"]
        assert data["eq"] is True

    def test_different_images_differ(self) -> None:
        """Distinct fixture images must not share checksums (anti-hardcode)."""
        images = sorted(FIXTURES.glob("*.png"))
        assert len(images) >= 2
        out = _ruby(
            f"""
require_relative '/app/config/boot'
a = ImageFeatureExtractor.extract('{images[0]}')
b = ImageFeatureExtractor.extract('{images[1]}')
puts JSON.generate({{'a' => a[:checksum], 'b' => b[:checksum]}})
"""
        )
        data = json.loads(out)
        assert data["a"] != data["b"]

    def test_serializer_field_order_and_no_timestamps(self) -> None:
        """FeatureSerializer emits keys in width/height/mean_rgb/checksum order without timestamps."""
        image = sorted(FIXTURES.glob("*.png"))[0]
        out = _ruby(
            f"""
require_relative '/app/config/boot'
f = ImageFeatureExtractor.extract('{image}')
puts FeatureSerializer.serialize(f)
"""
        )
        assert '"timestamp"' not in out
        assert '"created_at"' not in out
        keys = re.findall(r'"(\w+)"\s*:', out)
        assert keys == ["width", "height", "mean_rgb", "checksum"], keys
        parsed = json.loads(out)
        assert set(parsed.keys()) == {"width", "height", "mean_rgb", "checksum"}

    def test_injection_novel_image(self) -> None:
        """Extractor must handle a novel ImageMagick-generated file not in the seed set."""
        novel = Path("/tmp/fv_novel_m1.png")
        subprocess.run(
            ["convert", "-size", "40x30", "xc:#112233", str(novel)],
            check=True,
            timeout=60,
        )
        try:
            out = _ruby(
                f"""
require_relative '/app/config/boot'
f = ImageFeatureExtractor.extract('{novel}')
puts JSON.generate({{'w' => f[:width], 'h' => f[:height], 'c' => f[:checksum], 'm' => f[:mean_rgb]}})
"""
            )
            data = json.loads(out)
            assert data["w"] == 224 and data["h"] == 224
            assert data["c"]
            assert data["m"][2] >= data["m"][0]
        finally:
            novel.unlink(missing_ok=True)

    def test_checksum_includes_source_dimensions(self) -> None:
        """Checksum must change when source image dimensions differ (policy prefix rule)."""
        a = Path("/tmp/fv_dim_a.png")
        b = Path("/tmp/fv_dim_b.png")
        subprocess.run(["convert", "-size", "20x20", "xc:#aabbcc", str(a)], check=True)
        subprocess.run(["convert", "-size", "40x20", "xc:#aabbcc", str(b)], check=True)
        try:
            out = _ruby(
                f"""
require_relative '/app/config/boot'
ca = ImageFeatureExtractor.extract('{a}')[:checksum]
cb = ImageFeatureExtractor.extract('{b}')[:checksum]
puts JSON.generate({{'a' => ca, 'b' => cb}})
"""
            )
            data = json.loads(out)
            assert data["a"] != data["b"]
        finally:
            a.unlink(missing_ok=True)
            b.unlink(missing_ok=True)

    def test_checksum_is_exact_sha256(self) -> None:
        """Checksum must equal SHA256 of `<W>x<H>:` prefix plus resized RGB bytes."""
        known = Path("/tmp/fv_sha256_known.png")
        rgb_path = Path("/tmp/fv_sha256_known.rgb")
        subprocess.run(
            ["convert", "-size", "32x24", "xc:#c0ffee", str(known)],
            check=True,
            timeout=60,
        )
        try:
            ident = subprocess.run(
                ["identify", "-format", "%w %h", str(known)],
                capture_output=True,
                text=True,
                check=True,
                timeout=30,
            )
            orig_w, orig_h = ident.stdout.strip().split()
            subprocess.run(
                [
                    "convert",
                    str(known),
                    "-resize",
                    "224x224!",
                    "-depth",
                    "8",
                    f"rgb:{rgb_path}",
                ],
                check=True,
                timeout=60,
            )
            pixels = rgb_path.read_bytes()
            assert len(pixels) == 224 * 224 * 3
            expected = hashlib.sha256(f"{orig_w}x{orig_h}:".encode() + pixels).hexdigest()
            out = _ruby(
                f"""
require_relative '/app/config/boot'
puts ImageFeatureExtractor.extract('{known}')[:checksum]
"""
            )
            assert out == expected
            assert len(out) == 64
        finally:
            known.unlink(missing_ok=True)
            rgb_path.unlink(missing_ok=True)
