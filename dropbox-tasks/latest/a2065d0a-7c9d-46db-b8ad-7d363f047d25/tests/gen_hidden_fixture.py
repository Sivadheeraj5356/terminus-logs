"""Generate hidden corpora that exercise independent failure modes.

Each corpus lives under /opt/verifier-fixtures/lda and targets a different layer
of the documented contract:

- lexical: vocabulary/document ordering plus duplicate-token frequencies.
- burnin: a corpus whose retained theta differs if burn-in sweeps are included.
- ranking: a concentrated corpus whose top-term slots require lexical tie-breaks.
"""
from pathlib import Path
import json
import shutil

root = Path("/opt/verifier-fixtures/lda")
shutil.rmtree(root, ignore_errors=True)
for name in ("lexical", "burnin", "ranking"):
    (root / name).mkdir(parents=True)


def write(directory: Path, filename: str, doc_id: str, tokens: list[str]) -> None:
    (directory / filename).write_text(json.dumps({"doc_id": doc_id, "tokens": tokens}))


# lexical: file names deliberately disagree with doc_id order; tokens are heavily
# repeated and lexically scattered so vocabulary sorting and token ids matter.
lexical = root / "lexical"
write(lexical, "f1.json", "PX-40", ["zeta", "alpha", "zeta", "mu", "alpha", "zeta"])
write(lexical, "f2.json", "PX-10", ["mu", "beta", "beta", "alpha", "mu", "beta"])
write(lexical, "f3.json", "PX-30", ["kappa", "zeta", "kappa", "alpha", "kappa", "mu"])
write(lexical, "f4.json", "PX-20", ["beta", "delta", "delta", "beta", "alpha", "delta"])

# burnin: enough tokens and structure that early (burn-in) sweeps carry a
# different per-document distribution than the retained sweeps.
burnin = root / "burnin"
write(burnin, "b1.json", "BR-3", ["engine", "valve", "engine", "piston", "valve", "engine", "piston"])
write(burnin, "b2.json", "BR-1", ["rotor", "stator", "rotor", "winding", "stator", "rotor", "winding"])
write(burnin, "b3.json", "BR-2", ["engine", "rotor", "valve", "stator", "piston", "winding", "engine"])
write(burnin, "b4.json", "BR-4", ["turbine", "blade", "turbine", "shaft", "blade", "turbine", "shaft"])

# ranking: two tokens dominate, the rest appear once, so every topic leaves
# several zero-count terms that must fill the top slots by ascending token order.
ranking = root / "ranking"
write(ranking, "r1.json", "RK-2", ["aa", "aa", "aa", "bb", "aa", "aa"])
write(ranking, "r2.json", "RK-1", ["bb", "bb", "bb", "aa", "bb", "bb"])
write(ranking, "r3.json", "RK-3", ["aa", "bb", "cc", "dd", "ee", "ff"])
