"""Build sealed bootyard and bootorder fixtures for verifier cases."""
from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text, encoding="utf-8")


def link(path: Path, target: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() or path.is_symlink():
        path.unlink()
    path.symlink_to(target)


def _identity(host="checkout", machine="a"*32, gen=0, default="multi-user.target"):
    lines = [
        "format=bootyard.v1",
        f"host_label={host}",
        f"machine_id={machine}",
        "architecture=x86_64",
        f"initial_generation={gen}",
        f"default_target={default}",
        "admin_roots=etc/systemd/system",
        "max_unit_files=160",
        "max_dropins=240",
        "max_admin_symlinks=260",
        "max_devices=120",
        "max_directives=4000",
        "max_arcs=2000",
        "max_intent_ops=48",
        "max_targets=12",
        "max_yard_bytes=8388608",
        "previous_state=",
        "immutable_digest=" + ("0"*64),
    ]
    return "\n".join(lines) + "\n"


def _facts(**extra):
    base = {
        "architecture": "x86_64",
        "virtualization": "kvm",
        "firmware": "uefi",
        "hostname": "checkout",
        "machine_id": "a"*32,
        "boot_id": "b"*32,
        "first_boot": "false",
        "env_flags": "none",
    }
    base.update(extra)
    lines = [f"{k}={v}" for k, v in base.items()]
    return "\n".join(lines) + "\n"


def seal_order_members(intent, preset, accept, seal_body="seal"):
    seal = sha256_text(seal_body)
    blob = f"unit.intent\n{intent}preset.selection\n{preset}acceptance.jobs\n{accept}order.seal\n{seal}\n"
    # normalize: members already include trailing newlines from write helpers
    if not intent.endswith("\n"):
        intent += "\n"
    if not preset.endswith("\n"):
        preset += "\n"
    if not accept.endswith("\n"):
        accept += "\n"
    seal_line = seal + "\n"
    blob = f"unit.intent\n{intent}preset.selection\n{preset}acceptance.jobs\n{accept}order.seal\n{seal_line}"
    digest = sha256_text(blob)
    return digest, seal


def build_trivial_yard(root: Path, gen: int = 0) -> Path:
    """One static service wanted by multi-user.target."""
    root.mkdir(parents=True, exist_ok=True)
    write(root / "yard.identity", _identity(gen=gen))
    write(root / "vendor.seal", "app.service\tfile\t0644\t" + sha256_text("[Unit]\nDescription=app\n") + "\n")
    write(root / "runtime.facts", _facts() + "service_outcome=app.service\tsuccess\n")
    write(root / "proc.cmdline", "cmdline=BOOT_IMAGE=/vmlinuz root=UUID=1\n")
    write(root / "devices.table", "")
    write(
        root / "usr/lib/systemd/system/app.service",
        "[Unit]\nDescription=app\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n",
    )
    write(
        root / "usr/lib/systemd/system/multi-user.target",
        "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=app.service\n",
    )
    link(root / "etc/systemd/system/multi-user.target.wants/app.service", "../app.service")
    # alias fragment into admin for relative link resolution
    link(root / "etc/systemd/system/app.service", "/usr/lib/systemd/system/app.service")
    # Actually relative only — fix to relative copy as file
    (root / "etc/systemd/system/app.service").unlink(missing_ok=True)
    write(
        root / "etc/systemd/system/app.service",
        "[Unit]\nDescription=app\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n",
    )
    write(root / "var/lib/unitgraph/generation", f"{gen}\n")
    return root


def build_trivial_order(root: Path, yard_host="checkout", machine="a"*32, gen=0) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    intent = "1\tENABLE\tapp.service\t-\tenabled\t-\tenabled\t-\n"
    # ENABLE when already enabled is ok / or empty intent for pure boot
    intent = ""  # no mutations; just reconcile boot graph
    preset = ""
    accept = "app.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=app.service\n"
    members_digest, seal = seal_order_members(intent, preset, accept)
    record = "\n".join([
        "format=bootorder.v1",
        "order_id=ord-trivial-001",
        f"yard_host_label={yard_host}",
        f"yard_machine_id={machine}",
        f"expected_generation={gen}",
        f"next_generation={gen+1}",
        "final_target=multi-user.target",
        "job_mode=fail",
        "max_intent_ops=48",
        f"members_digest={members_digest}",
    ]) + "\n"
    write(root / "order.record", record)
    write(root / "unit.intent", intent if intent else "")
    write(root / "preset.selection", preset if preset else "")
    write(root / "acceptance.jobs", accept)
    write(root / "order.seal", seal + "\n")
    return root


def build_yard_with_features(root: Path, scenario: str, gen: int = 0) -> Path:
    """Scenario-specific yards for the 37-case docket."""
    root.mkdir(parents=True, exist_ok=True)
    write(root / "yard.identity", _identity(gen=gen))
    write(root / "proc.cmdline", "cmdline=BOOT_IMAGE=/vmlinuz quiet\n")
    facts = _facts()
    # common targets
    write(root / "usr/lib/systemd/system/multi-user.target", "[Unit]\nDescription=mu\nDefaultDependencies=no\n")
    write(root / "usr/lib/systemd/system/basic.target", "[Unit]\nDescription=basic\nDefaultDependencies=no\n")
    write(root / "usr/lib/systemd/system/local-fs.target", "[Unit]\nDescription=lfs\nDefaultDependencies=no\n")
    write(root / "var/lib/unitgraph/generation", f"{gen}\n")

    if scenario in ("trivial", "integrated", "idempotent", "relocated", "receipt", "cold", "change_account"):
        write(root / "runtime.facts", facts + "service_outcome=app.service\tsuccess\n")
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/app.service",
              "[Unit]\nDescription=app\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/app.service",
              "[Unit]\nDescription=app\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\n\n[Service]\nType=oneshot\n")
        link(root / "etc/systemd/system/multi-user.target.wants/app.service", "../app.service")
        return root

    if scenario == "tier_pref":
        write(root / "runtime.facts", facts + "service_outcome=demo.service\tsuccess\n")
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/demo.service", "[Unit]\nDescription=vendor\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n")
        write(root / "run/systemd/system/demo.service", "[Unit]\nDescription=transient\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/demo.service", "[Unit]\nDescription=admin\nDefaultDependencies=no\nWants=\n\n[Service]\nType=oneshot\n")
        write(root / "usr/lib/systemd/system/multi-user.target",
              "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=demo.service\n")
        link(root / "etc/systemd/system/multi-user.target.wants/demo.service", "../demo.service")
        return root

    if scenario == "mask_alias":
        write(root / "runtime.facts", facts)
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/real.service", "[Unit]\nDescription=real\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n")
        link(root / "etc/systemd/system/alias.service", "real.service")
        link(root / "run/systemd/system/masked.service", "/dev/null")
        write(root / "usr/lib/systemd/system/multi-user.target",
              "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=alias.service\n")
        link(root / "etc/systemd/system/multi-user.target.wants/alias.service", "../alias.service")
        return root

    if scenario == "template":
        write(root / "runtime.facts", facts + "service_outcome=worker@one.service\tsuccess\n")
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/worker@.service",
              "[Unit]\nDescription=worker %i\nDefaultDependencies=no\n\n[Service]\nType=oneshot\nSyslogIdentifier=%p_%i\n")
        write(root / "usr/lib/systemd/system/multi-user.target",
              "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=worker@one.service\n")
        write(root / "etc/systemd/system/worker@.service",
              "[Unit]\nDescription=worker %i\nDefaultDependencies=no\n\n[Service]\nType=oneshot\nSyslogIdentifier=%p_%i\n")
        link(root / "etc/systemd/system/multi-user.target.wants/worker@one.service", "../worker@.service")
        return root

    if scenario == "mount_device":
        write(root / "runtime.facts", facts + "path_fact=/data\tdir\nmount_fact=/data\text4\n")
        write(root / "devices.table", "dev-disk.device\tready\tbk1\tuuid:abcd,dev:disk1\n")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/data.mount",
              "[Unit]\nDescription=data\nDefaultDependencies=no\n\n[Mount]\nWhat=uuid:abcd\nWhere=/data\nType=ext4\n")
        write(root / "usr/lib/systemd/system/multi-user.target",
              "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=data.mount\n")
        write(root / "etc/systemd/system/data.mount",
              "[Unit]\nDescription=data\nDefaultDependencies=no\n\n[Mount]\nWhat=uuid:abcd\nWhere=/data\nType=ext4\n")
        link(root / "etc/systemd/system/multi-user.target.wants/data.mount", "../data.mount")
        return root

    if scenario == "condition":
        write(root / "runtime.facts", facts + "path_fact=/opt/flag\tmissing\nservice_outcome=gated.service\tsuccess\n")
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/gated.service",
              "[Unit]\nDescription=gated\nDefaultDependencies=no\nConditionPathExists=/opt/flag\n\n[Service]\nType=oneshot\n")
        write(root / "usr/lib/systemd/system/asserted.service",
              "[Unit]\nDescription=asserted\nDefaultDependencies=no\nAssertPathExists=/opt/flag\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/gated.service",
              "[Unit]\nDescription=gated\nDefaultDependencies=no\nConditionPathExists=/opt/flag\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/asserted.service",
              "[Unit]\nDescription=asserted\nDefaultDependencies=no\nAssertPathExists=/opt/flag\n\n[Service]\nType=oneshot\n")
        write(root / "usr/lib/systemd/system/multi-user.target",
              "[Unit]\nDescription=mu\nDefaultDependencies=no\nWants=gated.service asserted.service\n")
        link(root / "etc/systemd/system/multi-user.target.wants/gated.service", "../gated.service")
        link(root / "etc/systemd/system/multi-user.target.wants/asserted.service", "../asserted.service")
        return root

    if scenario == "enable_disable":
        write(root / "runtime.facts", facts + "service_outcome=pkg.service\tsuccess\n")
        write(root / "devices.table", "")
        write(root / "vendor.seal", "sealed\n")
        write(root / "usr/lib/systemd/system/pkg.service",
              "[Unit]\nDescription=pkg\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\nAlso=pkg-helper.service\n\n[Service]\nType=oneshot\n")
        write(root / "usr/lib/systemd/system/pkg-helper.service",
              "[Unit]\nDescription=helper\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/pkg.service",
              "[Unit]\nDescription=pkg\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\nAlso=pkg-helper.service\n\n[Service]\nType=oneshot\n")
        write(root / "etc/systemd/system/pkg-helper.service",
              "[Unit]\nDescription=helper\nDefaultDependencies=no\n\n[Install]\nWantedBy=multi-user.target\n\n[Service]\nType=oneshot\n")
        return root

    # default fallback trivial
    return build_yard_with_features(root, "trivial", gen)


def build_order_for(root: Path, scenario: str, gen: int = 0, order_id: str | None = None) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    oid = order_id or f"ord-{scenario}-001"
    machine = "a" * 32
    host = "checkout"
    intent = ""
    preset = ""
    if scenario == "enable_disable":
        intent = "1\tENABLE\tpkg.service\t-\tdisabled\t-\tenabled\t-\n"
        accept = "pkg.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=pkg.service\n"
    elif scenario == "condition":
        accept = "gated.service\tSKIPPED\tcondition-failed\nasserted.service\tFAILED\tassert-failed\nmulti-user.target\tSTARTED\tstarted\n"
    elif scenario == "mount_device":
        accept = "data.mount\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=data.mount\n"
    elif scenario == "tier_pref":
        accept = "demo.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=demo.service\n"
    elif scenario == "template":
        accept = "worker@one.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=worker@one.service\n"
    elif scenario == "mask_alias":
        accept = "alias.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=alias.service\n"
    elif scenario == "stale_gen":
        accept = "app.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\n"
        # expected gen wrong
        gen_for_record = gen + 5
        members_digest, seal = seal_order_members(intent, preset, accept)
        record = "\n".join([
            "format=bootorder.v1",
            f"order_id={oid}",
            f"yard_host_label={host}",
            f"yard_machine_id={machine}",
            f"expected_generation={gen_for_record}",
            f"next_generation={gen_for_record+1}",
            "final_target=multi-user.target",
            "job_mode=fail",
            "max_intent_ops=48",
            f"members_digest={members_digest}",
        ]) + "\n"
        write(root / "order.record", record)
        write(root / "unit.intent", intent)
        write(root / "preset.selection", preset)
        write(root / "acceptance.jobs", accept)
        write(root / "order.seal", seal + "\n")
        return root
    else:
        accept = "app.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\ntarget_member=app.service\n"

    members_digest, seal = seal_order_members(intent, preset, accept)
    record = "\n".join([
        "format=bootorder.v1",
        f"order_id={oid}",
        f"yard_host_label={host}",
        f"yard_machine_id={machine}",
        f"expected_generation={gen}",
        f"next_generation={gen+1}",
        "final_target=multi-user.target",
        "job_mode=fail",
        "max_intent_ops=48",
        f"members_digest={members_digest}",
    ]) + "\n"
    write(root / "order.record", record)
    write(root / "unit.intent", intent)
    write(root / "preset.selection", preset)
    write(root / "acceptance.jobs", accept)
    write(root / "order.seal", seal + "\n")
    return root
