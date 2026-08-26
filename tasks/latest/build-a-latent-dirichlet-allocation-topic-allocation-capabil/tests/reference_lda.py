"""Independent Python reference for the LDA collapsed-Gibbs topic allocator.

Nothing here imports the Rust workspace. It is a clean re-derivation of the
documented contract: corpus staging (sorted vocabulary and documents), the
deterministic xorshift64* collapsed-Gibbs sampler, the posterior count ledger,
burn-in retained theta accumulation, smoothed topic-term ranking, and the sealed
rollup export. The behavioral verifier compares the compiled ldactl artifacts
against the values produced here.
"""
from __future__ import annotations

import hashlib
import json
import tomllib
from pathlib import Path

CONFIG = Path("/app/config/ldactl.toml")
COUNTS_SEPARATOR = b"\n--counts--\n"
MASK = (1 << 64) - 1
MULT = 0x2545F4914F6CDD1D
TWO53 = 9007199254740992


def params() -> dict:
    """Read the sampler hyperparameters from the shipped service configuration."""
    data = tomllib.loads(CONFIG.read_text())
    return {
        "k": int(data["topics"]),
        "alpha": float(data["alpha"]),
        "beta": float(data["beta"]),
        "sweeps": int(data["sweeps"]),
        "burn_in": int(data["burn_in"]),
        "seed": int(data["seed"]),
        "top_terms": int(data["top_terms"]),
    }


def _read_doc(path: Path) -> dict:
    raw = json.loads(path.read_text())
    doc_id = str(raw["doc_id"])
    if not doc_id:
        raise ValueError("empty doc_id")
    tokens = [str(t) for t in raw["tokens"]]
    if not tokens or any(not t for t in tokens):
        raise ValueError("invalid tokens")
    return {"doc_id": doc_id, "tokens": tokens}


def corpus_staging(root: Path) -> dict:
    """Ingest every JSON document under root into the canonical corpus snapshot."""
    docs = [_read_doc(p) for p in sorted(Path(root).glob("*.json"))]
    if not docs:
        raise ValueError("empty inbox")
    seen: set[str] = set()
    for doc in docs:
        if doc["doc_id"] in seen:
            raise ValueError("duplicate doc_id")
        seen.add(doc["doc_id"])
    vocab = sorted({t for doc in docs for t in doc["tokens"]})
    index = {t: i for i, t in enumerate(vocab)}
    staged = sorted(
        (
            {"doc_id": doc["doc_id"], "token_ids": [index[t] for t in doc["tokens"]]}
            for doc in docs
        ),
        key=lambda x: x["doc_id"],
    )
    return {"schema": "lda-corpus/v1", "vocab": vocab, "docs": staged}


class _Rng:
    """xorshift64* generator matching /app/docs/initialization.md exactly."""

    def __init__(self, seed: int) -> None:
        self.state = seed if seed != 0 else 0x9E3779B97F4A7C15

    def next_u64(self) -> int:
        x = self.state
        x ^= x >> 12
        x &= MASK
        x ^= (x << 25) & MASK
        x &= MASK
        x ^= x >> 27
        x &= MASK
        self.state = x
        return (x * MULT) & MASK

    def uniform(self) -> float:
        return (self.next_u64() >> 11) * (1.0 / TWO53)


def count_staging(corpus: dict, p: dict | None = None) -> dict:
    """Run the documented collapsed-Gibbs sampler over a corpus snapshot."""
    if p is None:
        p = params()
    k = p["k"]
    alpha = p["alpha"]
    beta = p["beta"]
    sweeps = p["sweeps"]
    burn_in = p["burn_in"]
    vocab = corpus["vocab"]
    v = len(vocab)
    docs = corpus["docs"]
    d = len(docs)
    doc_ids = [doc["doc_id"] for doc in docs]
    token_ids = [list(doc["token_ids"]) for doc in docs]

    n_dk = [[0] * k for _ in range(d)]
    n_kw = [[0] * v for _ in range(k)]
    n_k = [0] * k
    theta_sum = [[0.0] * k for _ in range(d)]
    assignments = [[0] * len(row) for row in token_ids]

    rng = _Rng(p["seed"])
    for di in range(d):
        for i, w in enumerate(token_ids[di]):
            topic = rng.next_u64() % k
            n_dk[di][topic] += 1
            n_kw[topic][w] += 1
            n_k[topic] += 1
            assignments[di][i] = topic

    for sweep in range(1, sweeps + 1):
        for di in range(d):
            row = token_ids[di]
            for i in range(len(row)):
                w = row[i]
                old = assignments[di][i]
                n_dk[di][old] -= 1
                n_kw[old][w] -= 1
                n_k[old] -= 1
                masses = [0.0] * k
                total = 0.0
                for topic in range(k):
                    mass = (n_dk[di][topic] + alpha) * (n_kw[topic][w] + beta) / (
                        n_k[topic] + v * beta
                    )
                    masses[topic] = mass
                    total += mass
                draw = rng.uniform() * total
                new = k - 1
                cumulative = 0.0
                for topic in range(k):
                    cumulative += masses[topic]
                    if cumulative > draw:
                        new = topic
                        break
                n_dk[di][new] += 1
                n_kw[new][w] += 1
                n_k[new] += 1
                assignments[di][i] = new
        if sweep > burn_in:
            for di in range(d):
                total_counts = sum(n_dk[di])
                denom = total_counts + k * alpha
                for topic in range(k):
                    theta_sum[di][topic] += (n_dk[di][topic] + alpha) / denom

    retained = sweeps - burn_in
    return {
        "schema": "lda-counts/v1",
        "k": k,
        "alpha": alpha,
        "beta": beta,
        "seed": p["seed"],
        "sweeps": sweeps,
        "burn_in": burn_in,
        "retained_sweeps": retained,
        "vocab": vocab,
        "doc_ids": doc_ids,
        "assignments": assignments,
        "n_dk": n_dk,
        "n_kw": n_kw,
        "n_k": n_k,
        "theta_sum": theta_sum,
    }


def top_terms(n_kw_row: list[int], n_k_topic: int, vocab: list[str], beta: float, count: int) -> list[dict]:
    """Rank a topic's terms by smoothed posterior probability."""
    v = len(vocab)
    denom = n_k_topic + v * beta
    items = [(tok, (n_kw_row[w] + beta) / denom) for w, tok in enumerate(vocab)]
    items.sort(key=lambda t: (-t[1], t[0]))
    return [{"token": tok, "probability": prob} for tok, prob in items[:count]]


def rollup(corpus_bytes: bytes, count_bytes: bytes, p: dict | None = None) -> dict:
    """Build the sealed topic rollup from the two exact state snapshots."""
    if p is None:
        p = params()
    counts = json.loads(count_bytes)
    k = counts["k"]
    vocab = counts["vocab"]
    beta = counts["beta"]
    retained = counts["retained_sweeps"]
    topics = [
        {
            "topic": topic,
            "top_terms": top_terms(
                counts["n_kw"][topic], counts["n_k"][topic], vocab, beta, p["top_terms"]
            ),
        }
        for topic in range(k)
    ]
    documents = []
    for di, doc_id in enumerate(counts["doc_ids"]):
        theta = [s / retained for s in counts["theta_sum"][di]]
        total = sum(theta)
        theta = [t / total for t in theta]
        documents.append({"doc_id": doc_id, "theta": theta})
    return {
        "schema": "lda-rollup/v1",
        "retained_sweeps": retained,
        "topics": topics,
        "documents": documents,
        "snapshot_checksum": checksum(corpus_bytes, count_bytes),
    }


def checksum(corpus_bytes: bytes, count_bytes: bytes) -> str:
    return hashlib.sha256(corpus_bytes + COUNTS_SEPARATOR + count_bytes).hexdigest()
