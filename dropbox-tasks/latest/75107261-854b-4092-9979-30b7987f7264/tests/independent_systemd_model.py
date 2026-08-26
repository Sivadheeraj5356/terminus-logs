"""Independent Python interpretation of the eight contracts (correct semantics)."""
from __future__ import annotations

from pathlib import Path


def expect_success_trivial(yard: Path) -> bool:
    return (yard / "etc/systemd/system/multi-user.target.wants/app.service").exists() or (
        yard / "etc/systemd/system/multi-user.target.wants/app.service"
    ).is_symlink()


def classify_condition_outcomes():
    return {"condition": "skip", "assert": "fail"}


def mount_root_name():
    return "-.mount"


def tier_order():
    return ["admin", "transient", "vendor"]


def specifier_instance_pair():
    """Escaped (%i) then unescaped (%I) instance forms."""
    return ("%i", "%I")
