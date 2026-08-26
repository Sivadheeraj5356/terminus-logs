"""Build graded registries for the replace and exclude milestone.

Each builder writes a registry plus a main manifest carrying the directive under
test into a fresh temp directory and returns (registry_dir, main_path). The
registries also exercise the rule that replace and exclude written in a
dependency manifest are inert, only the main module's directives take effect.
"""

import os
import tempfile


def _write(root, rel, text):
    path = os.path.join(root, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        f.write(text)


def make(name):
    """Return (registry_dir, main_path) for the named fixture."""
    root = tempfile.mkdtemp(prefix=f"mv_m3_{name}_")
    reg = os.path.join(root, "reg")
    main_text, extra = _BUILDERS[name](reg, root)
    main_path = os.path.join(root, "main.mod")
    with open(main_path, "w") as f:
        f.write(main_text)
    return reg, main_path


def _bare(name, lang="1.16", requires=(), replaces=(), excludes=()):
    lines = [f"module {name}", f"lang {lang}"]
    for path, ver in requires:
        lines.append(f"require {path} {ver}")
    for line in replaces:
        lines.append(f"replace {line}")
    for path, ver in excludes:
        lines.append(f"exclude {path} {ver}")
    return "\n".join(lines) + "\n"


def _replace_downgrade(reg, root):
    # A requires C v1.2.0, B requires C v1.3.0. Without replace C is v1.3.0. The
    # main module replaces C v1.3.0 with C v1.1.0, below the required maximum.
    _write(reg, "A@v1.0.0/module.mod", _bare("A", requires=[("C", "v1.2.0")]))
    _write(reg, "B@v1.0.0/module.mod", _bare("B", requires=[("C", "v1.3.0")]))
    for v in ("v1.1.0", "v1.2.0", "v1.3.0"):
        _write(reg, f"C@{v}/module.mod", _bare("C"))
    return (
        _bare(
            "app",
            requires=[("A", "v1.0.0"), ("B", "v1.0.0")],
            replaces=["C v1.3.0 => C v1.1.0"],
        ),
        None,
    )


def _replace_versionless(reg, root):
    # A versionless replace rewrites every version of the module. C is required
    # at v1.2.0 but replaced wholesale with v1.0.0.
    _write(reg, "A@v1.0.0/module.mod", _bare("A", requires=[("C", "v1.2.0")]))
    for v in ("v1.0.0", "v1.2.0"):
        _write(reg, f"C@{v}/module.mod", _bare("C"))
    return (
        _bare("app", requires=[("A", "v1.0.0")], replaces=["C => C v1.0.0"]),
        None,
    )


def _replace_to_local(reg, root):
    # main requires A. main replaces A with a local directory whose manifest adds
    # a new requirement D that the registry version of A never had. D must appear
    # and the registry A requirement on C must vanish.
    _write(reg, "A@v1.0.0/module.mod", _bare("A", requires=[("C", "v1.0.0")]))
    _write(reg, "C@v1.0.0/module.mod", _bare("C"))
    _write(reg, "D@v1.0.0/module.mod", _bare("D"))
    local = os.path.join(root, "local", "a")
    os.makedirs(local, exist_ok=True)
    with open(os.path.join(local, "module.mod"), "w") as f:
        f.write(_bare("A", requires=[("D", "v1.0.0")]))
    return (
        _bare("app", requires=[("A", "v1.0.0")], replaces=["A => ./local/a"]),
        None,
    )


def _exclude_next_highest(reg, root):
    # A requires C v1.2.0. main excludes C v1.2.0. Registry has v1.1.0, v1.2.0,
    # v1.3.0. Selection falls to the next required and not excluded higher
    # version, v1.3.0.
    _write(reg, "A@v1.0.0/module.mod", _bare("A", requires=[("C", "v1.2.0")]))
    for v in ("v1.1.0", "v1.2.0", "v1.3.0"):
        _write(reg, f"C@{v}/module.mod", _bare("C"))
    return (
        _bare("app", requires=[("A", "v1.0.0")], excludes=[("C", "v1.2.0")]),
        None,
    )


def _dependency_directives_ignored(reg, root):
    # A's own manifest carries a replace and an exclude on C. Both are inert. C is
    # selected at the required v1.2.0.
    _write(
        reg,
        "A@v1.0.0/module.mod",
        _bare(
            "A",
            requires=[("C", "v1.2.0")],
            replaces=["C v1.2.0 => C v1.1.0"],
            excludes=[("C", "v1.2.0")],
        ),
    )
    for v in ("v1.1.0", "v1.2.0"):
        _write(reg, f"C@{v}/module.mod", _bare("C"))
    return (_bare("app", requires=[("A", "v1.0.0")]), None)


def _exclude_with_replace_unaffected(reg, root):
    # Combined: main excludes C v1.2.0 and replaces B's required edge. A requires
    # C v1.2.0 (excluded -> next highest v1.3.0); B requires E v2.0.0 but main
    # replaces E v2.0.0 with E v1.5.0.
    _write(reg, "A@v1.0.0/module.mod", _bare("A", requires=[("C", "v1.2.0")]))
    _write(reg, "B@v1.0.0/module.mod", _bare("B", requires=[("E", "v2.0.0")]))
    for v in ("v1.1.0", "v1.2.0", "v1.3.0"):
        _write(reg, f"C@{v}/module.mod", _bare("C"))
    for v in ("v1.5.0", "v2.0.0"):
        _write(reg, f"E@{v}/module.mod", _bare("E"))
    return (
        _bare(
            "app",
            requires=[("A", "v1.0.0"), ("B", "v1.0.0")],
            replaces=["E v2.0.0 => E v1.5.0"],
            excludes=[("C", "v1.2.0")],
        ),
        None,
    )


_BUILDERS = {
    "replace_downgrade": _replace_downgrade,
    "replace_versionless": _replace_versionless,
    "replace_to_local": _replace_to_local,
    "exclude_next_highest": _exclude_next_highest,
    "dependency_directives_ignored": _dependency_directives_ignored,
    "exclude_with_replace": _exclude_with_replace_unaffected,
}
