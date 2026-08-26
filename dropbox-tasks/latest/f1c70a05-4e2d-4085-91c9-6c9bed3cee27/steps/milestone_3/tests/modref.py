"""Independent reference implementation of the modverse resolver.

This module recomputes every ground truth quantity the verifier needs: the total
order over version strings, the manifest model, the build list, and the loaded
manifest set. It is deliberately a separate implementation from the Scala under
test and lives only under the mounted test directory, never under /app. The
verifier compares the agent's CLI output against what this module computes from
the same inputs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------

PSEUDO_RE = re.compile(r"\d{14}-[0-9a-f]{12}$")


@dataclass(frozen=True)
class Version:
    raw: str  # without a leading v

    @property
    def display(self) -> str:
        return "v" + self.raw

    def __lt__(self, other: "Version") -> bool:
        return compare(self, other) < 0


def parse_version(s: str) -> Version:
    t = s.strip()
    if t.startswith("v"):
        t = t[1:]
    return Version(t)


def _split_core(raw: str):
    """Return (major, minor, patch, suffix, is_incompatible).

    suffix is the prerelease text without the leading '-', or None.
    """
    is_incompat = False
    body = raw
    if body.endswith("+incompatible"):
        is_incompat = True
        body = body[: -len("+incompatible")]
    if "+" in body:
        raise ValueError(f"bad build metadata in version: {raw}")
    if "-" in body:
        core, suffix = body.split("-", 1)
    else:
        core, suffix = body, None
    parts = core.split(".")
    if len(parts) != 3:
        raise ValueError(f"bad numeric core: {raw}")
    major, minor, patch = (int(p) for p in parts)
    return major, minor, patch, suffix, is_incompat


def _classify(suffix: Optional[str]):
    """Return (rank, kind) where lower rank sorts lower within an equal core.

    rank: 0 pseudo, 1 prerelease, 2 plain release, 3 incompatible (handled by
    the caller for incompatible).
    """
    if suffix is None:
        return 2
    if PSEUDO_RE.search(suffix):
        return 0
    return 1


def _cmp_prerelease(a: str, b: str) -> int:
    aids = a.split(".")
    bids = b.split(".")
    for ai, bi in zip(aids, bids):
        an = ai.isdigit()
        bn = bi.isdigit()
        if an and bn:
            c = (int(ai) > int(bi)) - (int(ai) < int(bi))
            if c != 0:
                return c
        elif an and not bn:
            return -1
        elif bn and not an:
            return 1
        else:
            c = (ai > bi) - (ai < bi)
            if c != 0:
                return c
    return (len(aids) > len(bids)) - (len(aids) < len(bids))


def _pseudo_key(suffix: str):
    m = PSEUDO_RE.search(suffix)
    chunk = m.group(0)
    ts, sh = chunk.split("-", 1)
    return int(ts), sh


def compare(a: Version, b: Version) -> int:
    if a.raw == b.raw:
        return 0
    amaj, amin, apat, asuf, ainc = _split_core(a.raw)
    bmaj, bmin, bpat, bsuf, binc = _split_core(b.raw)
    for x, y in ((amaj, bmaj), (amin, bmin), (apat, bpat)):
        if x != y:
            return -1 if x < y else 1
    # equal numeric core
    arank = 3 if ainc else _classify(asuf)
    brank = 3 if binc else _classify(bsuf)
    if arank != brank:
        return -1 if arank < brank else 1
    if arank == 0:
        ak = _pseudo_key(asuf)
        bk = _pseudo_key(bsuf)
        if ak[0] != bk[0]:
            return -1 if ak[0] < bk[0] else 1
        if ak[1] != bk[1]:
            return -1 if ak[1] < bk[1] else 1
        return 0
    if arank == 1:
        return _cmp_prerelease(asuf, bsuf)
    return 0


def vmax(a: Version, b: Version) -> Version:
    return a if compare(a, b) >= 0 else b


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

@dataclass
class Require:
    path: str
    version: Version
    indirect: bool


@dataclass
class Replace:
    old_path: str
    old_version: Optional[Version]
    new_path: str
    new_version: Optional[Version]
    new_is_local: bool


@dataclass
class Exclude:
    path: str
    version: Version


@dataclass
class Manifest:
    module: str = ""
    lang: tuple = (0, 0)
    requires: list = field(default_factory=list)
    replaces: list = field(default_factory=list)
    excludes: list = field(default_factory=list)


def _strip_comment_tail(line: str):
    """Return (content, indirect_flag). Honour a trailing // indirect marker."""
    idx = line.find("//")
    if idx < 0:
        return line, False
    tail = line[idx + 2 :].strip()
    return line[:idx], tail == "indirect"


def parse_manifest(text: str) -> Manifest:
    m = Manifest()
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        i += 1
        stripped = raw.strip()
        if not stripped or stripped.startswith("//"):
            continue
        if stripped.startswith("module "):
            m.module = stripped[len("module ") :].strip()
        elif stripped.startswith("lang "):
            val = stripped[len("lang ") :].strip()
            a, b = val.split(".")
            m.lang = (int(a), int(b))
        elif stripped.startswith("require"):
            rest = stripped[len("require") :].strip()
            if rest == "(":
                while i < len(lines):
                    body = lines[i]
                    i += 1
                    bs = body.strip()
                    if bs == ")":
                        break
                    if not bs or bs.startswith("//"):
                        continue
                    m.requires.append(_parse_require_entry(bs))
            else:
                m.requires.append(_parse_require_entry(rest))
        elif stripped.startswith("replace"):
            rest = stripped[len("replace") :].strip()
            if rest == "(":
                while i < len(lines):
                    body = lines[i]
                    i += 1
                    bs = body.strip()
                    if bs == ")":
                        break
                    if not bs or bs.startswith("//"):
                        continue
                    m.replaces.append(_parse_replace_entry(bs))
            else:
                m.replaces.append(_parse_replace_entry(rest))
        elif stripped.startswith("exclude"):
            rest = stripped[len("exclude") :].strip()
            if rest == "(":
                while i < len(lines):
                    body = lines[i]
                    i += 1
                    bs = body.strip()
                    if bs == ")":
                        break
                    if not bs or bs.startswith("//"):
                        continue
                    m.excludes.append(_parse_exclude_entry(bs))
            else:
                m.excludes.append(_parse_exclude_entry(rest))
        else:
            raise ValueError(f"unrecognised manifest line: {stripped}")
    return m


def _parse_require_entry(s: str) -> Require:
    content, indirect = _strip_comment_tail(s)
    toks = content.split()
    if len(toks) != 2:
        raise ValueError(f"bad require entry: {s}")
    return Require(toks[0], parse_version(toks[1]), indirect)


def _parse_replace_entry(s: str) -> Replace:
    content, _ = _strip_comment_tail(s)
    if "=>" not in content:
        raise ValueError(f"bad replace entry: {s}")
    left, right = content.split("=>", 1)
    lt = left.split()
    rt = right.split()
    old_path = lt[0]
    old_version = parse_version(lt[1]) if len(lt) >= 2 else None
    new_path = rt[0]
    is_local = new_path.startswith("./") or new_path.startswith("../")
    new_version = None
    if not is_local and len(rt) >= 2:
        new_version = parse_version(rt[1])
    return Replace(old_path, old_version, new_path, new_version, is_local)


def _parse_exclude_entry(s: str) -> Exclude:
    content, _ = _strip_comment_tail(s)
    toks = content.split()
    if len(toks) != 2:
        raise ValueError(f"bad exclude entry: {s}")
    return Exclude(toks[0], parse_version(toks[1]))


# ---------------------------------------------------------------------------
# Build list
# ---------------------------------------------------------------------------

LANG_PRUNE_THRESHOLD = (1, 17)


class Registry:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        self.loaded: list[str] = []
        self._cache: dict[str, Manifest] = {}

    def rel_path(self, module: str, version: Version) -> str:
        return f"{module}@{version.display}/module.mod"

    def has(self, module: str, version: Version) -> bool:
        return os.path.isfile(os.path.join(self.root, self.rel_path(module, version)))

    def available_versions(self, module: str) -> list[Version]:
        out = []
        parent = os.path.dirname(module)
        base = os.path.join(self.root, parent) if parent else self.root
        leaf = os.path.basename(module)
        if not os.path.isdir(base):
            return out
        for name in os.listdir(base):
            if name.startswith(leaf + "@"):
                vtext = name[len(leaf) + 1 :]
                if os.path.isfile(os.path.join(base, name, "module.mod")):
                    out.append(parse_version(vtext))
        return out

    def read_rel(self, rel: str) -> Manifest:
        if rel not in self.loaded:
            self.loaded.append(rel)
        if rel in self._cache:
            return self._cache[rel]
        with open(os.path.join(self.root, rel)) as f:
            man = parse_manifest(f.read())
        self._cache[rel] = man
        return man

    def read_module(self, module: str, version: Version) -> Manifest:
        return self.read_rel(self.rel_path(module, version))

    def read_at(self, path: str, recorded_as: Optional[str]) -> Manifest:
        if recorded_as is not None and recorded_as not in self.loaded:
            self.loaded.append(recorded_as)
        with open(path) as f:
            return parse_manifest(f.read())


def resolve(registry: Registry, main_path: str):
    """Return (build_list dict module->Version, loaded list of rel paths).

    The walk seeds from the main module and expands modules from a worklist. A
    module is expanded by reading its manifest at its currently selected version
    and folding every require into selection. Whether a required module is itself
    queued for expansion depends on the lang of the manifest that required it: an
    unpruned manifest below the threshold expands its requires so the full
    transitive closure is read, while a pruned manifest at or above the threshold
    folds its requires into selection but does not queue them, because it already
    enumerates its indirect requirements. The main module always queues its own
    direct requires regardless of its lang.
    """
    main = registry.read_at(os.path.abspath(main_path), None)

    main_replaces = main.replaces
    main_excludes = main.excludes

    def is_excluded(module: str, version: Version) -> bool:
        for e in main_excludes:
            if e.path == module and compare(e.version, version) == 0:
                return True
        return False

    def replacement_for(module: str, version: Version):
        """Return the main module replace directive that applies to this module
        version, or None. A version less replace matches every version.
        """
        chosen = None
        for r in main_replaces:
            if r.old_path == module and (
                r.old_version is None or compare(r.old_version, version) == 0
            ):
                chosen = r
        return chosen

    def manifest_source(module: str, version: Version):
        """Resolve the manifest to read for this module version after main module
        replace. Return (local_path_or_None, recorded_as, registry_module,
        registry_version, effective_build_version).

        effective_build_version is the version that should appear in the build
        list for this module: the replacement target version for a registry
        target replace, otherwise the selected version.
        """
        chosen = replacement_for(module, version)
        if chosen is None:
            return None, registry.rel_path(module, version), module, version, version
        if chosen.new_is_local:
            local_dir = os.path.normpath(
                os.path.join(
                    os.path.dirname(os.path.abspath(main_path)), chosen.new_path
                )
            )
            local_file = os.path.join(local_dir, "module.mod")
            if os.path.commonpath([registry.root, local_file]) == registry.root:
                recorded = os.path.relpath(local_file, registry.root)
            else:
                recorded = chosen.new_path
            return local_file, recorded, module, version, version
        nm = chosen.new_path
        nv = chosen.new_version
        return None, registry.rel_path(nm, nv), nm, nv, nv

    # required_max holds the pure maximum of required versions per module, the
    # value the selection rule yields before any main module replace override.
    required_max: dict[str, Version] = {}

    def excluded_effective(module: str, version: Version) -> Version:
        if is_excluded(module, version):
            cands = [
                v
                for v in registry.available_versions(module)
                if not is_excluded(module, v) and compare(v, version) >= 0
            ]
            if not cands:
                return version
            best = cands[0]
            for c in cands[1:]:
                if compare(c, best) < 0:
                    best = c
            return best
        return version

    def bump(module: str, version: Version) -> None:
        v = excluded_effective(module, version)
        if module not in required_max or compare(v, required_max[module]) > 0:
            required_max[module] = v

    # The walk reads the manifest of every required (module, version) pair the
    # graph reaches, not only the finally selected version, because each required
    # version contributes its own requirements to selection. A worklist of pairs
    # drives this. queued tracks pairs already enqueued so each manifest is read
    # once.
    queued: set[tuple[str, str]] = set()
    work: list[tuple[str, Version]] = []

    def enqueue(module: str, version: Version) -> None:
        ev = excluded_effective(module, version)
        key = (module, ev.raw)
        if key not in queued:
            queued.add(key)
            work.append((module, ev))

    for r in main.requires:
        bump(r.path, r.version)
        enqueue(r.path, r.version)

    while work:
        module, version = work.pop()
        local_path, recorded, reg_module, reg_version, _ = manifest_source(
            module, version
        )
        if local_path is not None:
            man = registry.read_at(local_path, recorded)
        else:
            if not registry.has(reg_module, reg_version):
                continue
            man = registry.read_rel(recorded)
        pruned = man.lang >= LANG_PRUNE_THRESHOLD
        for req in man.requires:
            bump(req.path, req.version)
            if not pruned:
                enqueue(req.path, req.version)

    # Apply the main module replace override to produce the build list versions.
    selected: dict[str, Version] = {}
    for module, ver in required_max.items():
        _, _, _, _, eff = manifest_source(module, ver)
        selected[module] = eff

    return selected, list(registry.loaded)
