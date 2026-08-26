"""Pinned decoder-note integrity for the streaming CTC caption task."""
from pathlib import Path
import hashlib

NOTE_HASHES = {
    "alignment-and-confidence-note.md": "d0a582b42391ce28ba98c3dec4590bd59a6dc51633fccb2ba26281bc61fce09b",
    "ctc-prefix-probability-note.md": "8ac6fef90ca34f47bd30225a1c44344d572a13d31879c2926e0e01d0168200d2",
    "phrase-bias-note.md": "856888d919802d91f4f208ad5d8afa9b534eca16f0c0dad2d405aa2d8f79f2ef",
    "streaming-state-note.md": "cb30050d95bbdcf3c731ab8d173a18a9b41ec2eafb1d34642f9c6c19e1bbebaf",
}


def pytest_sessionstart(session):
    note_dir = Path("/app/decoder-notes")
    if not note_dir.exists():
        note_dir = Path(__file__).resolve().parents[1] / "environment" / "caption-beam-kernel" / "decoder-notes"
    for name, expected in NOTE_HASHES.items():
        assert hashlib.sha256((note_dir / name).read_bytes()).hexdigest() == expected
