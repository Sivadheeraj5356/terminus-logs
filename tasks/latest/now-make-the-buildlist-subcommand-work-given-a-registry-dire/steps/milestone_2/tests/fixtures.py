"""Build graded registries for the build list milestone into a temp directory.

The registries are defined inline here so they live only under the mounted test
directory, never under /app. Each builder returns (registry_dir, main_path). The
fixtures deliberately include versions that exist in the registry but are
required by nobody, and shapes where a backtracking style solver would pick a
different build list than the maximum of required versions.
"""

import os
import tempfile


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _module(name, lang="1.16", requires=()):
    lines = [f"module {name}", f"lang {lang}"]
    if requires:
        lines.append("require (")
        for path, ver in requires:
            lines.append(f"\t{path} {ver}")
        lines.append(")")
    return "\n".join(lines) + "\n"


def make(name):
    """Return (registry_dir, main_path) for the named build list fixture."""
    root = tempfile.mkdtemp(prefix=f"mv_m2_{name}_")
    reg = os.path.join(root, "reg")
    builder = _BUILDERS[name]
    main_text = builder(reg)
    main_path = os.path.join(root, "main.mod")
    with open(main_path, "w") as f:
        f.write(main_text)
    return reg, main_path


def _diamond(reg):
    # main needs A and B; A needs C v1.1.0, B needs C v1.2.0 -> C selects v1.2.0.
    # C v1.5.0 exists but is required by nobody and must not be selected.
    _write(reg, "A@v1.0.0/module.mod", _module("A", requires=[("C", "v1.1.0")]))
    _write(reg, "B@v1.0.0/module.mod", _module("B", requires=[("C", "v1.2.0")]))
    for v in ("v1.1.0", "v1.2.0", "v1.5.0"):
        _write(reg, f"C@{v}/module.mod", _module("C"))
    return _module("app", requires=[("A", "v1.0.0"), ("B", "v1.0.0")])


def _unrequired_latest(reg):
    # main needs A v1.0.0 only. A needs D v1.0.0. Registry has D up to v9.9.9 that
    # nobody requires. The selected D must be v1.0.0, not the latest available.
    _write(reg, "A@v1.0.0/module.mod", _module("A", requires=[("D", "v1.0.0")]))
    for v in ("v1.0.0", "v1.1.0", "v2.0.0", "v9.9.9"):
        _write(reg, f"D@{v}/module.mod", _module("D"))
    return _module("app", requires=[("A", "v1.0.0")])


def _deep_chain(reg):
    # A -> B -> C -> D -> E, each requiring the next at increasing versions. The
    # build list takes each at exactly the required version.
    _write(reg, "A@v1.0.0/module.mod", _module("A", requires=[("B", "v1.1.0")]))
    _write(reg, "B@v1.1.0/module.mod", _module("B", requires=[("C", "v1.2.0")]))
    _write(reg, "C@v1.2.0/module.mod", _module("C", requires=[("D", "v1.3.0")]))
    _write(reg, "D@v1.3.0/module.mod", _module("D", requires=[("E", "v1.4.0")]))
    _write(reg, "E@v1.4.0/module.mod", _module("E"))
    # decoy higher versions nobody requires
    _write(reg, "C@v2.0.0/module.mod", _module("C"))
    _write(reg, "E@v2.0.0/module.mod", _module("E"))
    return _module("app", requires=[("A", "v1.0.0")])


def _backtrack_foil(reg):
    # A solver that backtracks to satisfy constraints would behave differently.
    # main needs A v1.0.0 and X v1.0.0.
    # A needs B v1.0.0; B needs A v1.2.0 (mutual, higher A). So A = max(v1.0.0,
    # v1.2.0) = v1.2.0; A v1.2.0 needs B v1.3.0; B = max(v1.0.0, v1.3.0) = v1.3.0;
    # B v1.3.0 needs A v1.2.0 (stable). X just needs B v1.1.0 (lower, ignored).
    # The maximum of required wins with no search; the build list is fully
    # determined by the highest requirement reached.
    _write(reg, "A@v1.0.0/module.mod", _module("A", requires=[("B", "v1.0.0")]))
    _write(reg, "A@v1.2.0/module.mod", _module("A", requires=[("B", "v1.3.0")]))
    _write(reg, "B@v1.0.0/module.mod", _module("B", requires=[("A", "v1.2.0")]))
    _write(reg, "B@v1.3.0/module.mod", _module("B", requires=[("A", "v1.2.0")]))
    _write(reg, "B@v1.1.0/module.mod", _module("B"))
    _write(reg, "X@v1.0.0/module.mod", _module("X", requires=[("B", "v1.1.0")]))
    # decoys
    _write(reg, "A@v2.0.0/module.mod", _module("A"))
    _write(reg, "B@v2.0.0/module.mod", _module("B"))
    return _module("app", requires=[("A", "v1.0.0"), ("X", "v1.0.0")])


def _empty(reg):
    # main requires nothing.
    os.makedirs(reg, exist_ok=True)
    return _module("app")


def _incompatible_select(reg):
    # main needs A and B; A needs C v2.0.0, B needs C v2.0.0+incompatible.
    # The incompatible release ranks above the plain core, so C selects the
    # incompatible one.
    _write(reg, "A@v1.0.0/module.mod", _module("A", requires=[("C", "v2.0.0")]))
    _write(
        reg,
        "B@v1.0.0/module.mod",
        _module("B", requires=[("C", "v2.0.0+incompatible")]),
    )
    _write(reg, "C@v2.0.0/module.mod", _module("C"))
    _write(reg, "C@v2.0.0+incompatible/module.mod", _module("C"))
    return _module("app", requires=[("A", "v1.0.0"), ("B", "v1.0.0")])


_BUILDERS = {
    "diamond": _diamond,
    "unrequired_latest": _unrequired_latest,
    "deep_chain": _deep_chain,
    "backtrack_foil": _backtrack_foil,
    "empty": _empty,
    "incompatible_select": _incompatible_select,
}
