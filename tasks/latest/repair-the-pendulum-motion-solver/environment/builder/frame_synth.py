"""Deterministic frame-strip synthesis for the pendulum-recovery job database.

Each recovery job corresponds to a short capture of a swinging pendulum bob whose
horizontal displacement traces a damped cosine::

    x(t) = amplitude * exp(-decay * t) * cos(2 * pi * frequency * t)

The per-job oscillation parameters (frequency, decay constant, amplitude) live only
in this module. They drive rendering of the PNG frame strips and are never persisted
to the database: a downstream tracker recovers frequency and decay purely from
the decoded pixels.

A fixed subset of frames per job is noised or occluded so a tracker rejects them.
The set of degraded frame indices is chosen from a seeded RNG so the montages, and
therefore the expected rejected-frame counts, are byte-stable across builds.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

import numpy as np
from PIL import Image

# ---------------------------------------------------------------------------
# Pinned generation constants. Keep these aligned with report.py and the
# project tests; downstream verifier tolerances are derived from them.
# ---------------------------------------------------------------------------

NUM_RECOVERY_JOBS = 4
FRAMES_PER_STRIP = 48

# Geometry of a single frame cell (pixels). The bob is drawn as a filled dark
# disk on a light background for centroid tracking.
FRAME_WIDTH = 64
FRAME_HEIGHT = 64
BOB_RADIUS = 6

# Time base: each frame is one sample at a fixed cadence.
FRAME_INTERVAL_SECONDS = 0.05  # 20 fps capture

# Background / foreground intensities (grayscale, stored as RGB for clarity).
BACKGROUND_LEVEL = 235
BOB_LEVEL = 25

# Master RNG seed. Every stochastic choice (which frames to degrade, the noise
# pattern) is drawn from generators seeded off this constant so the produced
# database is reproducible bit-for-bit.
MASTER_SEED = 20240517


@dataclass(frozen=True)
class OscillationParameters:
    """Ground-truth motion for one job. Never written to the database."""

    job_id: int
    frequency_hz: float
    decay_per_second: float
    amplitude_fraction: float  # peak displacement as a fraction of usable half-width


@dataclass
class SynthesizedStrip:
    """Result of rendering one job's frame strip."""

    job_id: int
    png_bytes: bytes
    degraded_frame_indices: List[int] = field(default_factory=list)

    @property
    def rejected_frame_count(self) -> int:
        return len(self.degraded_frame_indices)


# ---------------------------------------------------------------------------
# Per-job ground truth. Frequencies and decay constants vary across jobs so that
# aggregation over jobs is meaningfully exercised downstream. Chosen so the bob
# completes a few visible cycles within FRAMES_PER_STRIP samples and the decay is
# perceptible but not so fast the motion vanishes early.
# ---------------------------------------------------------------------------

def _ground_truth_parameters() -> List[OscillationParameters]:
    return [
        OscillationParameters(job_id=1, frequency_hz=0.90, decay_per_second=0.35, amplitude_fraction=0.90),
        OscillationParameters(job_id=2, frequency_hz=1.30, decay_per_second=0.55, amplitude_fraction=0.85),
        OscillationParameters(job_id=3, frequency_hz=1.75, decay_per_second=0.80, amplitude_fraction=0.80),
        OscillationParameters(job_id=4, frequency_hz=2.20, decay_per_second=1.10, amplitude_fraction=0.75),
    ]


# Number of frames degraded per job. Fixed so downstream tests compare counts.
# assert exact rejected-frame counts. Index 0 maps to job_id 1, etc.
DEGRADED_FRAMES_PER_JOB = [5, 7, 6, 8]


def ground_truth_parameters() -> List[OscillationParameters]:
    """Public accessor for the per-job motion parameters (source-only)."""

    return _ground_truth_parameters()


def _bob_center_x(params: OscillationParameters, frame_index: int) -> float:
    """Horizontal pixel position of the bob center for a given frame."""

    t = frame_index * FRAME_INTERVAL_SECONDS
    half_span = (FRAME_WIDTH / 2.0) - BOB_RADIUS - 1
    displacement = (
        params.amplitude_fraction
        * half_span
        * np.exp(-params.decay_per_second * t)
        * np.cos(2.0 * np.pi * params.frequency_hz * t)
    )
    return (FRAME_WIDTH / 2.0) + displacement


def _render_clean_frame(params: OscillationParameters, frame_index: int) -> np.ndarray:
    """Render one clean frame: dark disk on a light field."""

    frame = np.full((FRAME_HEIGHT, FRAME_WIDTH), BACKGROUND_LEVEL, dtype=np.uint8)
    cx = _bob_center_x(params, frame_index)
    cy = FRAME_HEIGHT / 2.0

    ys = np.arange(FRAME_HEIGHT).reshape(-1, 1)
    xs = np.arange(FRAME_WIDTH).reshape(1, -1)
    inside = (xs - cx) ** 2 + (ys - cy) ** 2 <= BOB_RADIUS ** 2
    frame[inside] = BOB_LEVEL
    return frame


def _apply_noise(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Replace a frame with dense salt-and-pepper noise (bob untrackable)."""

    return rng.integers(0, 256, size=frame.shape, dtype=np.uint16).astype(np.uint8)


def _apply_occlusion(frame: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Blank the frame with an opaque mid-gray band covering the bob's track."""

    occluded = frame.copy()
    occluded[:, :] = 128
    return occluded


def _choose_degraded_indices(job_slot: int, rng: np.random.Generator) -> List[int]:
    """Pick which interior frames to degrade for a job.

    Endpoints (index 0 and the final frame) are always kept clean so that a
    tracker has stable anchors; the degraded frames are drawn from the interior.
    """

    count = DEGRADED_FRAMES_PER_JOB[job_slot]
    candidates = np.arange(1, FRAMES_PER_STRIP - 1)
    chosen = rng.choice(candidates, size=count, replace=False)
    return sorted(int(i) for i in chosen)


def synthesize_strip(params: OscillationParameters, job_slot: int) -> SynthesizedStrip:
    """Render one job's horizontal montage PNG and return it with metadata."""

    # Each job gets its own child RNG derived deterministically from the master
    # seed and the job slot so strips are independent yet reproducible.
    rng = np.random.default_rng(MASTER_SEED + 1000 * (job_slot + 1))
    degraded = set(_choose_degraded_indices(job_slot, rng))

    montage = np.full(
        (FRAME_HEIGHT, FRAME_WIDTH * FRAMES_PER_STRIP), BACKGROUND_LEVEL, dtype=np.uint8
    )

    for frame_index in range(FRAMES_PER_STRIP):
        frame = _render_clean_frame(params, frame_index)
        if frame_index in degraded:
            # Alternate degradation styles deterministically so both a noisy and
            # an occluded failure mode appear in each strip.
            if frame_index % 2 == 0:
                frame = _apply_occlusion(frame, rng)
            else:
                frame = _apply_noise(frame, rng)
        col = frame_index * FRAME_WIDTH
        montage[:, col : col + FRAME_WIDTH] = frame

    image = Image.fromarray(montage, mode="L")
    from io import BytesIO

    buffer = BytesIO()
    # optimize=True keeps encoding deterministic; PNG is lossless so decode is exact.
    image.save(buffer, format="PNG", optimize=True)
    return SynthesizedStrip(
        job_id=params.job_id,
        png_bytes=buffer.getvalue(),
        degraded_frame_indices=sorted(degraded),
    )


def synthesize_all() -> List[SynthesizedStrip]:
    """Render every job's frame strip in job order."""

    strips = []
    for slot, params in enumerate(ground_truth_parameters()):
        strips.append(synthesize_strip(params, slot))
    return strips
