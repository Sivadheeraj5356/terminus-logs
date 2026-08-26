import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

APP = Path(os.environ.get("APP_UNDER_TEST", "/app"))


def run(command, timeout=90):
    env = os.environ.copy()
    env["PATH"] = f"{APP / 'tools'}:{env.get('PATH', '')}"
    result = subprocess.run(
        command,
        cwd=APP,
        shell=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=timeout,
        env=env,
    )
    assert result.returncode == 0, (
        f"command failed: {command}\nSTDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    return result


def read_json(rel):
    return json.loads((APP / rel).read_text())


def write_json(rel, data):
    (APP / rel).write_text(json.dumps(data, indent=2) + "\n")


def sha256_bytes(body):
    script = (
        "const crypto=require('node:crypto');"
        "const chunks=[];"
        "process.stdin.on('data',c=>chunks.push(c));"
        "process.stdin.on('end',()=>process.stdout.write("
        "crypto.createHash('sha256').update(Buffer.concat(chunks)).digest('hex')));"
    )
    result = subprocess.run(
        ["node", "-e", script],
        input=body,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=APP,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr.decode()
    return result.stdout.decode().strip()


def digest(rel):
    return sha256_bytes((APP / rel).read_bytes())


def canonicalize(value):
    if isinstance(value, list):
        return [canonicalize(item) for item in value]
    if isinstance(value, dict):
        return {key: canonicalize(value[key]) for key in sorted(value)}
    return value


def content_digest(payload):
    return sha256_bytes((json.dumps(canonicalize(payload), separators=(",", ":")) + "\n").encode())


def reset_generated_state():
    shutil.rmtree(APP / "node_modules", ignore_errors=True)
    shutil.rmtree(APP / "reports", ignore_errors=True)
    for app_dir in (APP / "apps").iterdir():
        shutil.rmtree(app_dir / "node_modules", ignore_errors=True)
    for package_dir in (APP / "packages").iterdir():
        shutil.rmtree(package_dir / "node_modules", ignore_errors=True)
    for rel in ["generated/plan-graph.json", "offline-store/index.json"]:
        try:
            (APP / rel).unlink()
        except FileNotFoundError:
            pass
    shutil.rmtree(APP / "offline-store" / "tarballs", ignore_errors=True)


def read_ledger():
    lines = (APP / "state/migrate-journal.jsonl").read_text().splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def open_train_tip():
    trains = read_json("config/release-trains.json")["trains"]
    open_trains = [train for train in trains if train["status"] == "open"]
    open_trains.sort(key=lambda train: (-int(train["epoch"]), train["id"]))
    return open_trains[0]


def parse_lock_edges():
    edges = []
    current_importer = None
    current_dep = None
    in_importers = False
    for raw in (APP / "pnpm-lock.yaml").read_text().splitlines():
        if raw == "importers:":
            in_importers = True
            continue
        if raw.startswith("packages:"):
            break
        if not in_importers:
            continue
        if raw.startswith("  ") and raw.endswith(":") and not raw.startswith("    "):
            current_importer = raw.strip()[:-1].strip("'")
            current_dep = None
        elif raw.startswith("      ") and raw.endswith(":") and not raw.startswith("        "):
            current_dep = raw.strip()[:-1].strip("'")
        elif raw.startswith("        specifier:"):
            edges.append(
                {
                    "importer": current_importer,
                    "alias": current_dep,
                    "specifier": raw.split(": ", 1)[1],
                }
            )
        elif raw.startswith("        version:"):
            edges[-1]["version"] = raw.split(": ", 1)[1]
    return [edge for edge in edges if edge["importer"] != "."]


def full_replay():
    reset_generated_state()
    run("/app/tools/pnpm run resume")
    run("/app/tools/pnpm run seal")
    run("/app/tools/pnpm install --offline --frozen-lockfile")
    run("/app/tools/pnpm run build")
    run("/app/tools/pnpm run audit:seal")


@contextmanager
def restored_files(*relative_paths):
    snapshots = {rel: (APP / rel).read_text() for rel in relative_paths}
    try:
        yield
    finally:
        for rel, text in snapshots.items():
            (APP / rel).write_text(text)


def target_of(graph, importer, alias):
    return graph["importers"][importer][alias].removeprefix("workspace:").split("@*")[0]


class TestHarborMigrateReplay:
    def test_clean_replay_regenerates_plan_store_lock_journal_and_audit(self):
        """Wipe-and-replay regenerates plan-graph, store, lockfile, journal tip, and seal audit."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        store = read_json("offline-store/index.json")
        audit = read_json("reports/seal-audit.json")
        tip = read_ledger()[-1]
        assert graph["schema"] == "migrate-plan-graph-v1"
        assert store["schema"] == "migrate-store-index-v1"
        assert audit["schema"] == "migrate-audit-v1"
        assert tip["phase"] == "COMMIT"
        assert audit["errors"] == []
        assert tip["fingerprint"] == graph["fingerprint"]

    def test_active_train_follows_open_tip_not_stale_cache_or_archive(self):
        """Sealed train/epoch match the open tip; stale cache and archived trains do not win."""
        full_replay()
        tip = open_train_tip()
        graph = read_json("generated/plan-graph.json")
        cached = read_json("state/active-train.json")
        archived = read_json("config/archived-trains.json")
        assert graph["train"] == tip["id"]
        assert int(graph["epoch"]) == int(tip["epoch"])
        assert cached["id"] == tip["id"]
        assert int(cached["epoch"]) == int(tip["epoch"])
        assert tip["id"] != "train-west" or int(tip["epoch"]) != 4
        assert all(train["id"] != graph["train"] for train in archived["trains"])

    def test_channel_windows_and_per_importer_hints_select_distinct_runtimes(self):
        """Fixture importers keep distinct runtime/adapter/plugin targets under train windows."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        assert target_of(graph, "apps/console", "@harbor/runtime") == "runtime-canary"
        assert target_of(graph, "apps/worker", "@harbor/runtime") == "runtime-stable"
        assert target_of(graph, "apps/console", "@harbor/adapter") == "adapter-next"
        assert target_of(graph, "apps/worker", "@harbor/plugin") == "plugin-extra"
        assert "adapter-primary" not in {
            target_of(graph, "apps/console", "@harbor/adapter"),
            target_of(graph, "apps/worker", "@harbor/plugin"),
        }

    def test_extension_peers_enter_plan_store_and_build_summary(self):
        """Extension peers appear in plan peers, store keys, and build summary."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        store = read_json("offline-store/index.json")
        summary = read_json("reports/build-summary.json")
        assert set(graph["peers"]) == {"peer-logger", "peer-metrics"}
        assert summary["peers"] == graph["peers"]
        sealed_names = {pkg["name"] for pkg in graph["packages"]}
        assert {"peer-logger", "peer-metrics"}.issubset(sealed_names)
        store_names = {key.split("#", 1)[0].rsplit("@", 1)[0] for key in store["packages"]}
        assert {"peer-logger", "peer-metrics"}.issubset(store_names)
        assert summary["providers"]["consoleRuntime"] == "runtime-canary"
        assert summary["providers"]["consoleAdapter"] == "adapter-next"
        assert summary["providers"]["workerRuntime"] == "runtime-stable"
        assert summary["providers"]["workerPlugin"] == "plugin-extra"

    def test_lockfile_and_manifests_converge_with_plan_edges(self):
        """Lockfile importer edges and package.json dependencies match the plan-graph."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        edges = parse_lock_edges()
        expected_count = sum(len(value) for value in graph["importers"].values())
        assert len(edges) == expected_count
        for edge in edges:
            assert edge["specifier"] == graph["importers"][edge["importer"]][edge["alias"]]
            target = edge["specifier"].removeprefix("workspace:").split("@*")[0]
            pkg = next(item for item in graph["packages"] if item["name"] == target)
            link_rel = edge["version"].replace("link:", "")
            resolved = (APP / edge["importer"] / link_rel).resolve()
            assert resolved.samefile((APP / pkg["path"]).resolve())
            manifest = read_json(f"{edge['importer']}/package.json")
            assert manifest["dependencies"][edge["alias"]] == edge["specifier"]

    def test_store_payloads_embed_sorted_peers_and_evict_ghosts(self):
        """Store keys digest payloads that include sorted peers; prior ghost keys are gone."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        store = read_json("offline-store/index.json")
        extensions = {
            item["whenPackage"]: sorted(item["peerRequires"])
            for item in read_json("config/extensions.json")["extensions"]
        }
        for pkg in graph["packages"]:
            key = f"{pkg['name']}@{pkg['version']}#{pkg['contentDigest'][:16]}"
            assert key in store["packages"]
            record = store["packages"][key]
            payload = json.loads((APP / record["tarball"]).read_text())
            assert payload["markers"]["sealed"] is True
            assert payload["peers"] == extensions.get(pkg["name"], [])
            assert content_digest(payload) == pkg["contentDigest"]
            assert content_digest(payload) == record["contentDigest"]
        assert all(not key.startswith("adapter-legacy@") for key in store["packages"])

    def test_frozen_offline_install_recreates_importer_links(self):
        """Deleting node_modules and reinstalling offline recreates alias links."""
        full_replay()
        shutil.rmtree(APP / "node_modules", ignore_errors=True)
        for app_dir in (APP / "apps").iterdir():
            shutil.rmtree(app_dir / "node_modules", ignore_errors=True)
        run("/app/tools/pnpm install --offline --frozen-lockfile")
        graph = read_json("generated/plan-graph.json")
        for importer, edges in graph["importers"].items():
            for alias, spec in edges.items():
                target = spec.removeprefix("workspace:").split("@*")[0]
                link = APP / importer / "node_modules" / Path(alias)
                assert link.exists(), f"missing {link}"
                package = read_json(link / "package.json")
                assert package["name"] == target

    def test_resume_keeps_committed_prefix_and_records_train_abort_reason(self):
        """Resume preserves the committed journal prefix and appends interrupted_train_migrate."""
        prior_fp = "fp-ok"
        crash = "\n".join(
            [
                json.dumps({"seq": 1, "phase": "SNAPSHOT", "fingerprint": prior_fp}),
                json.dumps({"seq": 2, "phase": "STAGE", "keys": ["pkg@1.0.0"]}),
                json.dumps({"seq": 3, "phase": "PROMOTE", "train": "train-west"}),
                json.dumps({"seq": 4, "phase": "COMMIT", "fingerprint": prior_fp}),
                json.dumps({"seq": 5, "phase": "SNAPSHOT", "fingerprint": "fp-partial"}),
                json.dumps({"seq": 6, "phase": "STAGE", "partial": True, "keys": ["ghost@0.0.1"]}),
            ]
        )
        (APP / "state/migrate-journal.jsonl").write_text(crash + "\n")
        full_replay()
        events = read_ledger()
        assert any(event["phase"] == "COMMIT" and event.get("fingerprint") == prior_fp for event in events)
        abort = next(event for event in events if event["phase"] == "ABORT")
        assert abort["reason"] == "interrupted_train_migrate"
        tip = events[-1]
        assert tip["phase"] == "COMMIT"
        graph = read_json("generated/plan-graph.json")
        assert tip["fingerprint"] == graph["fingerprint"]

    def test_driver_cycle_is_idempotent_and_heals_tampered_surfaces(self):
        """Second resume+seal is byte-stable and heals tampered generated outputs."""
        full_replay()
        tracked = ["generated/plan-graph.json", "offline-store/index.json", "pnpm-lock.yaml"]
        before = {rel: digest(rel) for rel in tracked}
        run("/app/tools/pnpm run resume")
        run("/app/tools/pnpm run seal")
        assert {rel: digest(rel) for rel in tracked} == before
        write_json("generated/plan-graph.json", {"schema": "migrate-plan-graph-v1", "packages": []})
        write_json("offline-store/index.json", {"schema": "migrate-store-index-v1", "packages": {}})
        (APP / "pnpm-lock.yaml").write_text("lockfileVersion: '9.0'\nimporters: {}\n")
        run("/app/tools/pnpm run seal")
        assert {rel: digest(rel) for rel in tracked} == before

    def test_lowering_open_tip_epoch_evicts_canary_store_keys(self):
        """Closing the high epoch train flips selection and replaces canary store keys."""
        full_replay()
        with restored_files("config/release-trains.json", "state/active-train.json", "state/migrate-journal.jsonl"):
            trains = read_json("config/release-trains.json")
            for train in trains["trains"]:
                if train["id"] == "train-east":
                    train["status"] = "closed"
            write_json("config/release-trains.json", trains)
            reset_generated_state()
            run("/app/tools/pnpm run resume")
            run("/app/tools/pnpm run seal")
            graph = read_json("generated/plan-graph.json")
            assert graph["train"] == "train-west"
            assert int(graph["epoch"]) == 4
            assert target_of(graph, "apps/console", "@harbor/runtime") == "runtime-stable"
            assert target_of(graph, "apps/console", "@harbor/adapter") == "adapter-legacy"
            assert target_of(graph, "apps/worker", "@harbor/plugin") == "plugin-core"
            assert graph["peers"] == []
            store_names = {
                key.split("#", 1)[0].rsplit("@", 1)[0]
                for key in read_json("offline-store/index.json")["packages"]
            }
            assert "runtime-canary" not in store_names
            assert "adapter-next" not in store_names
            assert "peer-metrics" not in store_names

    def test_delayed_peerless_payload_fails_audit_until_resealed(self):
        """Peer-stripped store payloads fail audit until seal restores extension-aware digests."""
        full_replay()
        graph = read_json("generated/plan-graph.json")
        store = read_json("offline-store/index.json")
        canary = next(pkg for pkg in graph["packages"] if pkg["name"] == "runtime-canary")
        key = f"{canary['name']}@{canary['version']}#{canary['contentDigest'][:16]}"
        record = store["packages"][key]
        poisoned = {
            "name": canary["name"],
            "version": canary["version"],
            "path": canary["path"],
            "peers": [],
            "markers": {"sealed": True},
        }
        body = (json.dumps(canonicalize(poisoned), indent=2) + "\n").encode()
        (APP / record["tarball"]).write_bytes(body)
        store["packages"][key]["sha256"] = sha256_bytes(body)
        store["packages"][key]["bytes"] = len(body)
        store["packages"][key]["contentDigest"] = content_digest(poisoned)
        write_json("offline-store/index.json", store)
        bad = subprocess.run(
            "/app/tools/pnpm run audit:seal",
            cwd=APP,
            shell=True,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "PATH": f"{APP / 'tools'}:{os.environ.get('PATH', '')}"},
        )
        assert bad.returncode >= 1
        run("/app/tools/pnpm run seal")
        run("/app/tools/pnpm run audit:seal")
        healed = read_json("offline-store/index.json")
        healed_key = f"{canary['name']}@{canary['version']}#{canary['contentDigest'][:16]}"
        payload = json.loads((APP / healed["packages"][healed_key]["tarball"]).read_text())
        want_peers = next(
            sorted(item["peerRequires"])
            for item in read_json("config/extensions.json")["extensions"]
            if item["whenPackage"] == "runtime-canary"
        )
        assert payload["peers"] == want_peers
        audit = read_json("reports/seal-audit.json")
        assert audit["errors"] == []

    def test_reordered_migrate_hosts_do_not_change_selection(self):
        """Reordering migrate host records without changing hints keeps sealed targets."""
        full_replay()
        with restored_files("config/migrate-hosts.json"):
            hosts = read_json("config/migrate-hosts.json")
            before = read_json("generated/plan-graph.json")
            hosts["hosts"] = list(reversed(hosts["hosts"]))
            for host in hosts["hosts"]:
                host["bindings"] = dict(reversed(list(host["bindings"].items())))
            write_json("config/migrate-hosts.json", hosts)
            reset_generated_state()
            run("/app/tools/pnpm run resume")
            run("/app/tools/pnpm run seal")
            after = read_json("generated/plan-graph.json")
            assert after["importers"] == before["importers"]
            assert after["fingerprint"] == before["fingerprint"]
            assert after["peers"] == before["peers"]
            assert after["train"] == before["train"]
