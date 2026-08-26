"""Build graded registries for the pruning milestone.

The fixtures mix modules above and below the indirect tracking threshold so the
walk loads a different set of manifests depending on whether a chain sits behind
a properly versioned dependency. A properly versioned dependency records its
indirect requirements directly, so its deeper dependency manifests are pruned
from the walk while the build list stays correct. Builders return
(registry_dir, main_path).
"""

import os
import tempfile


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def _mod(name, lang, requires=()):
    lines = [f"module {name}", f"lang {lang}"]
    if requires:
        lines.append("require (")
        for path, ver, indirect in requires:
            marker = " // indirect" if indirect else ""
            lines.append(f"\t{path} {ver}{marker}")
        lines.append(")")
    return "\n".join(lines) + "\n"


def make(name):
    """Return (registry_dir, main_path) for the named pruning fixture."""
    root = tempfile.mkdtemp(prefix=f"mv_m4_{name}_")
    reg = os.path.join(root, "reg")
    main_text = _BUILDERS[name](reg)
    main_path = os.path.join(root, "main.mod")
    with open(main_path, "w") as f:
        f.write(main_text)
    return reg, main_path


def _pruned_chain(reg):
    # G is at the threshold and pre records its whole indirect closure. The deeper
    # manifests H, I, J must not be read, yet the build list still contains them.
    _write(
        reg,
        "G@v1.0.0/module.mod",
        _mod(
            "G",
            "1.17",
            requires=[
                ("H", "v1.0.0", False),
                ("I", "v1.0.0", True),
                ("J", "v1.0.0", True),
            ],
        ),
    )
    _write(reg, "H@v1.0.0/module.mod", _mod("H", "1.17", [("I", "v1.0.0", False)]))
    _write(reg, "I@v1.0.0/module.mod", _mod("I", "1.17", [("J", "v1.0.0", False)]))
    _write(reg, "J@v1.0.0/module.mod", _mod("J", "1.17"))
    return _mod("app", "1.17", [("G", "v1.0.0", False)])


def _unpruned_chain(reg):
    # The same chain below the threshold records nothing indirect, so the walk
    # must read the full transitive closure.
    _write(reg, "G@v1.0.0/module.mod", _mod("G", "1.16", [("H", "v1.0.0", False)]))
    _write(reg, "H@v1.0.0/module.mod", _mod("H", "1.16", [("I", "v1.0.0", False)]))
    _write(reg, "I@v1.0.0/module.mod", _mod("I", "1.16", [("J", "v1.0.0", False)]))
    _write(reg, "J@v1.0.0/module.mod", _mod("J", "1.16"))
    return _mod("app", "1.16", [("G", "v1.0.0", False)])


def _mixed(reg):
    # main needs P (threshold, pre records Q and R) and S (below threshold, needs
    # T which needs U). The walk reads P only on the pruned side but reads S, T, U
    # on the unpruned side. Build list contains P, Q, R, S, T, U.
    _write(
        reg,
        "P@v1.0.0/module.mod",
        _mod(
            "P",
            "1.20",
            requires=[("Q", "v1.0.0", False), ("R", "v1.0.0", True)],
        ),
    )
    _write(reg, "Q@v1.0.0/module.mod", _mod("Q", "1.20", [("R", "v1.0.0", False)]))
    _write(reg, "R@v1.0.0/module.mod", _mod("R", "1.20"))
    _write(reg, "S@v1.0.0/module.mod", _mod("S", "1.15", [("T", "v1.0.0", False)]))
    _write(reg, "T@v1.0.0/module.mod", _mod("T", "1.15", [("U", "v1.0.0", False)]))
    _write(reg, "U@v1.0.0/module.mod", _mod("U", "1.15"))
    return _mod("app", "1.17", [("P", "v1.0.0", False), ("S", "v1.0.0", False)])


def _pruned_drops_wrong_indirect(reg):
    # A pruned dependency K records its indirect requirement L. An implementation
    # that prunes too aggressively and drops the recorded indirect entry would
    # leave L out of the build list entirely, which is wrong. L's own manifest is
    # never read under correct pruning.
    _write(
        reg,
        "K@v1.0.0/module.mod",
        _mod("K", "1.18", [("L", "v2.0.0", True)]),
    )
    _write(reg, "L@v1.0.0/module.mod", _mod("L", "1.18", [("M", "v1.0.0", False)]))
    _write(reg, "L@v2.0.0/module.mod", _mod("L", "1.18", [("M", "v9.0.0", False)]))
    _write(reg, "M@v1.0.0/module.mod", _mod("M", "1.18"))
    _write(reg, "M@v9.0.0/module.mod", _mod("M", "1.18"))
    return _mod("app", "1.18", [("K", "v1.0.0", False)])


_BUILDERS = {
    "pruned_chain": _pruned_chain,
    "unpruned_chain": _unpruned_chain,
    "mixed": _mixed,
    "pruned_drops_wrong_indirect": _pruned_drops_wrong_indirect,
}
