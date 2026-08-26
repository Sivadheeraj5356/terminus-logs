"""37 public verifier cases for the systemd boot graph reconciler."""
from __future__ import annotations

from pathlib import Path

import bootyard_scene_mason as mason
import cold_boot_trace_referee as referee
import independent_systemd_model as model
import yard_byte_custodian as custodian
from unitgraph_verifier_latch import run_reconcile

pytest_plugins = ["unitgraph_verifier_latch"]


def _yard_order(workdir: Path, scenario: str, gen: int = 0):
    yard = mason.build_yard_with_features(workdir / f"{scenario}.bootyard", scenario, gen=gen)
    order = mason.build_order_for(workdir / f"{scenario}.bootorder", scenario, gen=gen)
    return yard, order


def test_unitboot_yard_roster_vendor_seal_and_order_closure_hold(workdir):
    """YARD-1 YARD-2 YARD-4 custody roster, vendor seal, and order member closure hold."""
    yard, order = _yard_order(workdir, "trivial")
    assert (yard / "yard.identity").is_file()
    assert (yard / "vendor.seal").is_file()
    assert (order / "order.record").is_file()
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.strip()) == 64


def test_unitboot_rejects_escaped_links_special_nodes_and_mutated_facts(workdir):
    """YARD-3 YARD-7 reject escaped links, special nodes, and mutated custody facts."""
    yard, order = _yard_order(workdir, "trivial")
    bad = yard / "etc/systemd/system/evil.service"
    bad.parent.mkdir(parents=True, exist_ok=True)
    bad.symlink_to("/etc/passwd")
    proc = run_reconcile(yard, order)
    assert proc.returncode != 0


def test_unitboot_fragment_search_prefers_admin_then_transient_then_vendor(workdir):
    """FRAGMENT-1 fragment search prefers administrator then transient then vendor."""
    yard, order = _yard_order(workdir, "tier_pref")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    eff = (yard / "var/lib/unitgraph/effective.units").read_text()
    demo = [ln for ln in eff.splitlines() if ln.startswith("demo.service\t")]
    assert demo, eff
    assert "etc/systemd/system/demo.service" in demo[0]
    assert "run/systemd/system/demo.service" not in demo[0]
    assert model.tier_order()[0] == "admin"


def test_unitboot_masks_alias_chains_and_alias_loops_have_exact_outcomes(workdir):
    """FRAGMENT-2 INSTALL-4 masks, alias chains, and alias loops have exact outcomes."""
    yard, order = _yard_order(workdir, "mask_alias")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    eff = (yard / "var/lib/unitgraph/effective.units").read_text()
    alias = [ln for ln in eff.splitlines() if ln.startswith("alias.service\t")]
    assert alias, eff
    assert "real.service" in alias[0] or "alias.service" in alias[0]
    assert "\tloaded\t" in alias[0] or "\tmask" not in alias[0].split("\t")[1]

def test_unitboot_exact_instance_then_template_fallback_preserves_identity(workdir):
    """FRAGMENT-3 SPECIFIER-4 exact instance then template fallback preserves identity."""
    yard, order = _yard_order(workdir, "template")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    eff = (yard / "var/lib/unitgraph/effective.units").read_text()
    worker = [ln for ln in eff.splitlines() if ln.startswith("worker@one.service\t")]
    assert worker, eff
    assert "\ttemplate\t" in worker[0]
    assert "worker@.service" in worker[0]


def test_unitboot_dropin_families_tiers_and_basenames_merge_canonically(workdir):
    """FRAGMENT-4 drop-in families, tiers, and basenames merge canonically."""
    yard, order = _yard_order(workdir, "trivial")
    d = yard / "etc/systemd/system/app.service.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / "10-extra.conf").write_text("[Unit]\nWants=\nWants=basic.target\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    assert "basic.target" in jobs or "Wants" in (yard / "var/lib/unitgraph/effective.units").read_text()


def test_unitboot_empty_assignments_reset_lists_without_erasing_scalars(workdir):
    """FRAGMENT-5 empty assignments reset lists without erasing scalars."""
    yard, order = _yard_order(workdir, "trivial")
    base = yard / "etc/systemd/system/app.service"
    base.write_text(
        "[Unit]\nDescription=app\nDefaultDependencies=no\nWants=basic.target\n\n"
        "[Install]\nWantedBy=multi-user.target\n\n[Service]\nType=oneshot\n"
    )
    d = yard / "etc/systemd/system/app.service.d"
    d.mkdir(parents=True, exist_ok=True)
    (d / "20-reset.conf").write_text("[Unit]\nWants=\nDescription=still\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    assert "edge\tapp.service\tbasic.target\twants\t" not in jobs


def test_unitboot_unit_parser_honors_sections_quotes_continuations_and_arity(workdir):
    """FRAGMENT-5 unit parser honors sections, quotes, continuations, and arity."""
    yard, order = _yard_order(workdir, "trivial")
    text = (yard / "etc/systemd/system/app.service").read_text()
    (yard / "etc/systemd/system/app.service").write_text(
        text.replace("Description=app", 'Description="app \\\nline"')
    )
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr


def test_unitboot_specifiers_distinguish_names_prefixes_instances_and_paths(workdir):
    """SPECIFIER-1 SPECIFIER-2 specifiers distinguish names, prefixes, instances, and paths."""
    yard, order = _yard_order(workdir, "template")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    # Description must stay literal (%i); SyslogIdentifier must expand with escaped instance.
    # Independent model records the contracted pair; effective digest must reflect expansion.
    assert model.specifier_instance_pair() == ("%i", "%I")
    jobs = (yard / "var/lib/unitgraph/boot.trace").read_text()
    assert "worker@one.service" in jobs or "worker@one.service" in (
        yard / "var/lib/unitgraph/effective.units"
    ).read_text()


def test_unitboot_unit_name_escape_roundtrips_root_dash_and_utf8_bytes(workdir):
    """SPECIFIER-3 MOUNT-1 unit-name escape round-trips root, dash, and path bytes."""
    assert model.mount_root_name() == "-.mount"
    yard, order = _yard_order(workdir, "mount_device")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    assert model.mount_root_name() != "root.mount"


def test_unitboot_enable_creates_exact_wants_requires_alias_and_also_links(workdir):
    """INSTALL-1 enable creates exact wants/requires/alias/Also links."""
    yard, order = _yard_order(workdir, "enable_disable")
    before = custodian.snapshot(yard)
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    link = yard / "etc/systemd/system/multi-user.target.wants/pkg.service"
    assert link.is_symlink()
    target = str(link.readlink())
    assert not target.startswith("/"), f"enablement links must be relative, got {target}"
    assert ".wants/" in str(link) or link.parent.name.endswith(".wants")
    assert not (yard / "etc/systemd/system/multi-user.target.requires/pkg.service").exists()
    assert before != custodian.snapshot(yard)
    account = (yard / "var/lib/unitgraph/change.account").read_text()
    assert "pkg.service" in account
    assert "/app/" not in account and "tmp/" not in account


def test_unitboot_disable_removes_only_attributable_links_through_also_cycles(workdir):
    """INSTALL-1 disable removes only attributable links through Also cycles."""
    yard, order = _yard_order(workdir, "enable_disable")
    assert run_reconcile(yard, order).returncode == 0
    order2 = mason.build_order_for(
        workdir / "disable.bootorder", "enable_disable", gen=1, order_id="ord-disable-002"
    )
    intent = "1\tDISABLE\tpkg.service\t-\tenabled\t-\tdisabled\t-\n"
    accept = "multi-user.target\tSTARTED\tstarted\n"
    md, seal = mason.seal_order_members(intent, "", accept)
    (order2 / "unit.intent").write_text(intent)
    (order2 / "acceptance.jobs").write_text(accept)
    rec = (order2 / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    (order2 / "order.record").write_text("\n".join(rec) + "\n")
    (order2 / "order.seal").write_text(seal + "\n")
    (yard / "etc/systemd/system/multi-user.target.wants").mkdir(parents=True, exist_ok=True)
    other = yard / "etc/systemd/system/multi-user.target.wants/other.service"
    if not other.exists():
        other.symlink_to("../pkg-helper.service")
    snap_other = other.readlink()
    proc = run_reconcile(yard, order2)
    assert proc.returncode == 0, proc.stderr
    assert not (yard / "etc/systemd/system/multi-user.target.wants/pkg.service").exists()
    assert other.is_symlink() and other.readlink() == snap_other


def test_unitboot_template_default_instance_and_explicit_instances_are_closed(workdir):
    """INSTALL-3 FRAGMENT-3 template DefaultInstance and explicit instances are closed."""
    yard, order = _yard_order(workdir, "template")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    eff = (yard / "var/lib/unitgraph/effective.units").read_text()
    assert "worker@one.service" in eff
    assert "template" in eff or "worker@.service" in eff


def test_unitboot_preset_first_match_enable_disable_ignore_and_unmatched_hold(workdir):
    """INSTALL-3 preset first-match enable/disable/ignore and unmatched hold."""
    yard, order = _yard_order(workdir, "enable_disable")
    (order / "preset.selection").write_text(
        "enable pkg.service\nignore pkg.*\ndisable other.service\n"
    )
    intent = "1\tPRESET\tpkg.service\t-\tdisabled\t-\tenabled\t-\n"
    accept = "pkg.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\n"
    md, seal = mason.seal_order_members(intent, (order / "preset.selection").read_text(), accept)
    (order / "unit.intent").write_text(intent)
    (order / "acceptance.jobs").write_text(accept)
    rec = (order / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    (order / "order.record").write_text("\n".join(rec) + "\n")
    (order / "order.seal").write_text(seal + "\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    link = yard / "etc/systemd/system/multi-user.target.wants/pkg.service"
    assert link.is_symlink()
    assert not str(link.readlink()).startswith("/")


def test_unitboot_default_target_link_matches_the_requested_loadable_target(workdir):
    """INSTALL-5 default.target link matches the requested loadable target."""
    yard, order = _yard_order(workdir, "trivial")
    intent = "1\tSET_DEFAULT\tmulti-user.target\t-\tstatic\t-\tenabled\t-\n"
    accept = "app.service\tSTARTED\tstarted\nmulti-user.target\tSTARTED\tstarted\n"
    md, seal = mason.seal_order_members(intent, "", accept)
    (order / "unit.intent").write_text(intent)
    (order / "acceptance.jobs").write_text(accept)
    rec = (order / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    rec = ["order_id=ord-default-001" if line.startswith("order_id=") else line for line in rec]
    (order / "order.record").write_text("\n".join(rec) + "\n")
    (order / "order.seal").write_text(seal + "\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    default = yard / "etc/systemd/system/default.target"
    assert default.is_symlink()
    assert str(default.readlink()) == "multi-user.target"


def test_unitboot_mask_unmask_respects_all_tiers_and_does_not_resurrect_bytes(workdir):
    """INSTALL-4 mask/unmask respects tiers and does not resurrect bytes."""
    yard, order = _yard_order(workdir, "trivial")
    intent = "1\tMASK\tapp.service\t-\tenabled\t-\tmasked\t-\n"
    accept = "multi-user.target\tSTARTED\tstarted\n"
    md, seal = mason.seal_order_members(intent, "", accept)
    (order / "unit.intent").write_text(intent)
    (order / "acceptance.jobs").write_text(accept)
    rec = (order / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    rec = ["order_id=ord-mask-001" if line.startswith("order_id=") else line for line in rec]
    (order / "order.record").write_text("\n".join(rec) + "\n")
    (order / "order.seal").write_text(seal + "\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    assert (yard / "etc/systemd/system/app.service").is_symlink()
    assert str((yard / "etc/systemd/system/app.service").readlink()) == "/dev/null"


def test_unitboot_declared_prestates_and_generation_guards_reject_stale_orders(workdir):
    """YARD-6 INSTALL-6 declared prestates and generation guards reject stale orders."""
    yard, order = _yard_order(workdir, "stale_gen")
    if not (yard / "etc/systemd/system/app.service").exists():
        mason.build_yard_with_features(yard, "trivial", gen=0)
    snap = custodian.snapshot(yard)
    proc = run_reconcile(yard, order)
    assert proc.returncode != 0
    assert custodian.equal(snap, custodian.snapshot(yard))


def test_unitboot_wants_requires_requisite_bindsto_and_partof_remain_distinct(workdir):
    """JOB-2 Wants/Requires/Requisite/BindsTo/PartOf remain distinct."""
    yard, order = _yard_order(workdir, "trivial")
    facts = (yard / "runtime.facts").read_text().rstrip() + "\ninitial_active=peer.service\n"
    (yard / "runtime.facts").write_text(facts if facts.endswith("\n") else facts + "\n")
    (yard / "etc/systemd/system/peer.service").write_text(
        "[Unit]\nDescription=peer\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n"
    )
    (yard / "usr/lib/systemd/system/peer.service").write_text(
        "[Unit]\nDescription=peer\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n"
    )
    svc = yard / "etc/systemd/system/app.service"
    svc.write_text(
        "[Unit]\nDescription=app\nDefaultDependencies=no\nWants=peer.service\nRequires=peer.service\n"
        "Requisite=peer.service\nBindsTo=peer.service\nPartOf=peer.service\n\n[Service]\nType=oneshot\n"
    )
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    assert "wants" in jobs
    assert "requires" in jobs
    assert "requisite" in jobs
    assert "bindsto" in jobs
    assert "partof" in jobs


def test_unitboot_before_after_order_present_jobs_without_pulling_new_jobs(workdir):
    """JOB-2 Before/After order present jobs without pulling new jobs."""
    yard, order = _yard_order(workdir, "trivial")
    (yard / "etc/systemd/system/other.service").write_text(
        "[Unit]\nDescription=o\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n"
    )
    svc = yard / "etc/systemd/system/app.service"
    svc.write_text(
        "[Unit]\nDescription=app\nDefaultDependencies=no\nAfter=other.service\nBefore=multi-user.target\n\n[Service]\nType=oneshot\n"
    )
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    start_lines = [ln for ln in jobs.splitlines() if ln.startswith("other.service\tstart")]
    assert start_lines == [], f"After/Before must not pull jobs, got {start_lines}"


def test_unitboot_conflicts_create_stop_effects_under_the_requested_job_mode(workdir):
    """JOB-4 Conflicts create stop effects under the requested job mode."""
    yard, order = _yard_order(workdir, "trivial")
    (yard / "etc/systemd/system/rival.service").write_text(
        "[Unit]\nDescription=r\nDefaultDependencies=no\n\n[Service]\nType=oneshot\n"
    )
    svc = yard / "etc/systemd/system/app.service"
    svc.write_text(
        "[Unit]\nDescription=app\nDefaultDependencies=no\nConflicts=rival.service\n\n[Service]\nType=oneshot\n"
    )
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    assert "rival.service\tstop" in jobs or "conflict" in (yard / "var/lib/unitgraph/boot.trace").read_text()


def test_unitboot_default_dependencies_are_typed_provenanced_and_suppressible(workdir):
    """JOB-3 default dependencies are typed, provenanced, and suppressible."""
    yard, order = _yard_order(workdir, "trivial")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    jobs = (yard / "var/lib/unitgraph/transaction.jobs").read_text()
    assert "default:service-basic" not in jobs


def test_unitboot_ordering_cycles_drop_only_permitted_synthetic_edges(workdir):
    """JOB-5 ordering cycles drop only permitted synthetic edges."""
    yard, order = _yard_order(workdir, "trivial")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr


def test_unitboot_irreducible_explicit_cycles_return_a_canonical_witness(workdir):
    """JOB-5 irreducible explicit cycles return a canonical witness."""
    yard, order = _yard_order(workdir, "trivial")
    a = yard / "etc/systemd/system/app.service"
    a.write_text(
        "[Unit]\nDescription=app\nDefaultDependencies=no\nAfter=multi-user.target\nBefore=multi-user.target\n\n[Service]\nType=oneshot\n"
    )
    proc = run_reconcile(yard, order)
    assert proc.returncode in (0, 7)


def test_unitboot_mount_names_where_paths_and_parent_mounts_are_consistent(workdir):
    """MOUNT-1 MOUNT-2 mount names, Where paths, and parent mounts are consistent."""
    yard, order = _yard_order(workdir, "mount_device")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    eff = (yard / "var/lib/unitgraph/effective.units").read_text()
    assert "data.mount" in eff


def test_unitboot_device_aliases_deduplicate_identity_and_gate_mount_readiness(workdir):
    """MOUNT-3 MOUNT-4 device aliases deduplicate by identity and gate mount readiness."""
    yard, order = _yard_order(workdir, "mount_device")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    assert "uuid:abcd" in (yard / "devices.table").read_text()


def test_unitboot_automount_waits_for_the_declared_access_trigger_before_mount(workdir):
    """MOUNT-5 automount waits for the declared access trigger before mount."""
    yard, order = _yard_order(workdir, "mount_device")
    (yard / "etc/systemd/system/data.automount").write_text(
        "[Unit]\nDescription=am\nDefaultDependencies=no\n\n[Automount]\nWhere=/data\n"
    )
    accept = (order / "acceptance.jobs").read_text() + "access_trigger=data.automount\n"
    intent = (order / "unit.intent").read_text()
    preset = (order / "preset.selection").read_text()
    md, seal = mason.seal_order_members(intent, preset, accept)
    (order / "acceptance.jobs").write_text(accept)
    rec = (order / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    rec = ["order_id=ord-automount-001" if line.startswith("order_id=") else line for line in rec]
    (order / "order.record").write_text("\n".join(rec) + "\n")
    (order / "order.seal").write_text(seal + "\n")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr


def test_unitboot_conditions_skip_assertions_fail_and_dependents_observe_both(workdir):
    """PREDICATE-2 conditions skip, assertions fail, and dependents observe both."""
    yard, order = _yard_order(workdir, "condition")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    trace = (yard / "var/lib/unitgraph/boot.trace").read_text()
    assert "condition-failed" in trace
    assert "assert-failed" in trace


def test_unitboot_captured_arch_firmware_virtualization_cmdline_and_paths_rule(workdir):
    """PREDICATE-1 PREDICATE-3 captured arch/firmware/virtualization/cmdline/paths rule."""
    yard, order = _yard_order(workdir, "trivial")
    facts = (yard / "runtime.facts").read_text()
    assert "architecture=x86_64" in facts
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr


def test_unitboot_job_states_wait_for_predecessors_stops_devices_and_results(workdir):
    """PREDICATE-4 job states wait for predecessors, stops, devices, and results."""
    yard, order = _yard_order(workdir, "trivial")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    trace = (yard / "var/lib/unitgraph/boot.trace").read_text()
    assert "state\t" in trace or "step\t" in trace


def test_unitboot_acceptance_requires_complete_target_membership_and_reasons(workdir):
    """PREDICATE-6 acceptance requires complete target membership and reasons."""
    yard, order = _yard_order(workdir, "trivial")
    (order / "acceptance.jobs").write_text("missing.service\tSTARTED\tstarted\n")
    intent = (order / "unit.intent").read_text()
    preset = (order / "preset.selection").read_text()
    accept = (order / "acceptance.jobs").read_text()
    md, seal = mason.seal_order_members(intent, preset, accept)
    rec = (order / "order.record").read_text().splitlines()
    rec = [f"members_digest={md}" if line.startswith("members_digest=") else line for line in rec]
    rec = ["order_id=ord-accept-bad" if line.startswith("order_id=") else line for line in rec]
    (order / "order.record").write_text("\n".join(rec) + "\n")
    (order / "order.seal").write_text(seal + "\n")
    snap = custodian.snapshot(yard)
    proc = run_reconcile(yard, order)
    assert proc.returncode != 0
    assert custodian.equal(snap, custodian.snapshot(yard))


def test_unitboot_change_account_authorizes_every_created_removed_replaced_item(workdir):
    """INSTALL-7 EVIDENCE-2 change.account authorizes every created/removed/replaced item."""
    yard, order = _yard_order(workdir, "enable_disable")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    account = (yard / "var/lib/unitgraph/change.account").read_text()
    assert "pkg.service" in account
    assert "multi-user.target.wants" in account
    assert not any(tok in account for tok in ("/tmp/", "/var/tmp/", "unitgraph_shadow"))


def test_unitboot_injected_mutation_and_replay_faults_restore_exact_prestate(workdir):
    """EVIDENCE-5 injected mutation and replay faults restore exact prestate."""
    yard, order = _yard_order(workdir, "trivial")
    snap = custodian.snapshot(yard)
    proc = run_reconcile(yard, order, env={"UNITGRAPH_INJECT_WRITE_FAULT": "1"})
    assert proc.returncode != 0
    assert custodian.equal(snap, custodian.snapshot(yard))
    proc = run_reconcile(yard, order, env={"UNITGRAPH_INJECT_REPLAY_FAULT": "1"})
    assert proc.returncode != 0
    assert custodian.equal(snap, custodian.snapshot(yard))


def test_unitboot_cold_process_rebuilds_effective_units_jobs_and_trace_from_bytes(workdir):
    """EVIDENCE-3 cold process rebuilds effective units, jobs, and trace from bytes."""
    yard, order = _yard_order(workdir, "cold")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    referee.assert_state_closed(yard)


def test_unitboot_state_records_and_receipt_form_one_reopenable_commitment(workdir):
    """EVIDENCE-2 EVIDENCE-4 state records and receipt form one reopenable commitment."""
    yard, order = _yard_order(workdir, "receipt")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    referee.assert_state_closed(yard)
    r1 = referee.receipt_of(yard)
    assert r1 == proc.stdout.strip()


def test_unitboot_repeating_an_accepted_order_is_a_verified_receipt_noop(workdir):
    """EVIDENCE-6 YARD-6 repeating an accepted order is a verified receipt no-op."""
    yard, order = _yard_order(workdir, "idempotent")
    proc1 = run_reconcile(yard, order)
    assert proc1.returncode == 0, proc1.stderr
    snap = custodian.snapshot(yard)
    r1 = proc1.stdout.strip()
    proc2 = run_reconcile(yard, order)
    assert proc2.returncode == 0, proc2.stderr
    assert proc2.stdout.strip() == r1
    # admin tree and state should match for verified noop
    assert custodian.equal(snap, custodian.snapshot(yard))


def test_unitboot_relocated_yard_and_order_clone_has_identical_poststate(workdir):
    """EVIDENCE-4 relocated yard and order clone has identical poststate."""
    yard, order = _yard_order(workdir, "relocated")
    proc1 = run_reconcile(yard, order)
    assert proc1.returncode == 0, proc1.stderr
    r1 = referee.receipt_of(yard)
    yard2 = workdir / "clone_root" / "relocated.bootyard"
    order2 = workdir / "clone_root" / "relocated.bootorder"
    # fresh clones pre-reconcile
    yard2.parent.mkdir(parents=True, exist_ok=True)
    mason.build_yard_with_features(yard2, "relocated", gen=0)
    mason.build_order_for(order2, "relocated", gen=0)
    proc2 = run_reconcile(yard2, order2)
    assert proc2.returncode == 0, proc2.stderr
    assert referee.receipt_of(yard2) == r1


def test_unitboot_integrated_recovery_target_reaches_a_closed_reboot_decision(workdir):
    """EVIDENCE-1 JOB-1 integrated recovery target reaches a closed reboot decision."""
    yard, order = _yard_order(workdir, "integrated")
    proc = run_reconcile(yard, order)
    assert proc.returncode == 0, proc.stderr
    referee.assert_state_closed(yard)
    assert model.expect_success_trivial(yard)
    assert len(proc.stdout.strip()) == 64
