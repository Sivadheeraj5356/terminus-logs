from __future__ import annotations

import ipaddress
import re
from pathlib import Path


TASK_FILE = Path("/app/task_file")
if not TASK_FILE.exists():
    TASK_FILE = Path(__file__).resolve().parents[1] / "environment" / "task_file"

ETC = TASK_FILE / "etc"
PAM = ETC / "pam.d"
SECURITY = ETC / "security"
SSH = ETC / "ssh" / "sshd_config"
SUDOERS = ETC / "sudoers.d" / "bastion"

USERS = {
    "alice": {"groups": {"vpn", "sudo"}},
    "bob": {"groups": {"vpn"}},
    "carol": {"groups": {"ops", "sudo"}},
    "dan": {"groups": {"ci"}},
    "erin": {"groups": {"contractor", "vpn"}},
    "frank": {"groups": {"ops", "breakglass"}},
    "root": {"groups": {"root"}},
}


def clean_lines(path: Path) -> list[str]:
    assert path.exists(), f"missing {path}"
    out: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        out.append(line)
    return out


def ssh_settings() -> dict[str, list[str]]:
    settings: dict[str, list[str]] = {}
    for line in clean_lines(SSH):
        parts = line.split()
        if not parts:
            continue
        key = parts[0].lower()
        settings.setdefault(key, []).append(" ".join(parts[1:]))
    return settings


def pam_entries(service: str) -> list[dict[str, object]]:
    entries: list[dict[str, object]] = []
    pattern = re.compile(r"^(?P<kind>\S+)\s+(?P<control>\[[^\]]+\]|\S+)\s+(?P<module>\S+)(?:\s+(?P<opts>.*))?$")
    for line in clean_lines(PAM / service):
        match = pattern.match(line)
        assert match, f"bad PAM line in {service}: {line}"
        opts = (match.group("opts") or "").split()
        entries.append(
            {
                "kind": match.group("kind"),
                "control": match.group("control"),
                "module": match.group("module"),
                "opts": opts,
                "line": line,
            }
        )
    return entries


def has_option(opts: list[str], key: str, value: str | None = None) -> bool:
    if value is None:
        return key in opts
    return f"{key}={value}" in opts


def entry_has_opts(entry: dict[str, object], required: tuple[str, ...]) -> bool:
    opts = entry["opts"]
    assert isinstance(opts, list)
    return all(token in opts for token in required)


def module_positions(service: str, module: str) -> list[int]:
    return [idx for idx, entry in enumerate(pam_entries(service)) if entry["module"] == module]


def principal_matches(pattern: str, user: str) -> bool:
    if pattern in {"ALL", "*"}:
        return True
    if pattern == user:
        return True
    if pattern.startswith("(") and pattern.endswith(")"):
        return pattern[1:-1] in USERS[user]["groups"]
    return False


def origin_matches(pattern: str, origin: str) -> bool:
    if pattern in {"ALL", "*"}:
        return True
    if pattern == origin:
        return True
    if pattern.startswith("*.") and origin.endswith(pattern[1:]):
        return True
    if "/" in pattern:
        try:
            return ipaddress.ip_address(origin) in ipaddress.ip_network(pattern, strict=False)
        except ValueError:
            return False
    return False


def access_allows(user: str, origin: str) -> bool:
    for line in clean_lines(SECURITY / "access.conf"):
        parts = line.split(":", 2)
        assert len(parts) == 3, f"bad access.conf line: {line}"
        effect, principal_text, origin_text = [part.strip() for part in parts]
        principals = principal_text.split()
        origins = origin_text.split()
        if any(principal_matches(p, user) for p in principals) and any(origin_matches(o, origin) for o in origins):
            return effect == "+"
    return False


DAY_TOKENS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su", "Al"]


def expand_days(day_expr: str) -> set[str]:
    days: set[str] = set()
    idx = 0
    while idx < len(day_expr):
        token = day_expr[idx : idx + 2]
        assert token in DAY_TOKENS, f"bad day token {token!r}"
        if token == "Al":
            days.update(DAY_TOKENS[:-1])
        else:
            days.add(token)
        idx += 2
    return days


def time_expr_matches(expr: str, weekday: str, minute: int) -> bool:
    match = re.fullmatch(r"([A-Za-z]+)(\d{4})-(\d{4})", expr)
    assert match, f"bad time expression: {expr}"
    days = expand_days(match.group(1))
    if weekday not in days:
        return False
    start = int(match.group(2)[:2]) * 60 + int(match.group(2)[2:])
    end = int(match.group(3)[:2]) * 60 + int(match.group(3)[2:])
    if start == end:
        return True
    if start < end:
        return start <= minute < end
    return minute >= start or minute < end


def time_allows(service: str, user: str, weekday: str, minute: int) -> bool:
    for line in clean_lines(SECURITY / "time.conf"):
        parts = [part.strip() for part in line.split(";")]
        assert len(parts) == 4, f"bad time.conf line: {line}"
        service_text, _tty_text, principal_text, time_text = parts
        services = service_text.split("|")
        principals = principal_text.split()
        if service not in services and "*" not in services:
            continue
        if not any(principal_matches(p, user) for p in principals):
            continue
        negated = time_text.startswith("!")
        expr = time_text[1:] if negated else time_text
        matched = time_expr_matches(expr, weekday, minute)
        if matched:
            return not negated
    return False


def group_allowed_by_sshd(user: str) -> bool:
    settings = ssh_settings()
    allowed: set[str] = set()
    for value in settings.get("allowgroups", []):
        allowed.update(value.split())
    return bool(USERS[user]["groups"] & allowed)


class TestSshdConfig:
    def test_ssh_daemon_is_pam_mfa_only(self) -> None:
        settings = ssh_settings()
        assert settings.get("usepam") == ["yes"]
        assert settings.get("passwordauthentication") == ["no"]
        assert settings.get("kbdinteractiveauthentication") == ["yes"]
        assert settings.get("permitrootlogin") == ["no"]
        auth_methods = " ".join(settings.get("authenticationmethods", []))
        assert "publickey,keyboard-interactive:pam" in auth_methods
        allow_groups = " ".join(settings.get("allowgroups", []))
        assert set(allow_groups.split()) == {"vpn", "ops", "breakglass", "ci"}
        for group in ("vpn", "ops", "breakglass", "ci"):
            assert group in allow_groups.split()
        assert "contractor" not in allow_groups.split()


class TestFaillockAndPam:
    def test_global_faillock_policy_is_strict(self) -> None:
        text = "\n".join(clean_lines(SECURITY / "faillock.conf"))
        for needle in ("deny = 3", "fail_interval = 900", "unlock_time = 900", "even_deny_root", "audit"):
            assert needle in text

    def test_each_stack_has_faillock_modes(self) -> None:
        for service in ("sshd", "sudo", "ci-deploy"):
            entries = pam_entries(service)
            faillock = [entry for entry in entries if entry["module"] == "pam_faillock.so"]
            assert len(faillock) >= 3, service
            opts = [set(entry["opts"]) for entry in faillock]
            assert any("preauth" in opt for opt in opts), service
            assert any("authfail" in opt for opt in opts), service
            assert any("authsucc" in opt for opt in opts), service

    def test_sshd_order_protects_breakglass_skip(self) -> None:
        entries = pam_entries("sshd")
        modules = [entry["module"] for entry in entries]
        unix = modules.index("pam_unix.so")
        access = modules.index("pam_access.so")
        pam_time = modules.index("pam_time.so")
        mfa = modules.index("pam_google_authenticator.so")
        breakglass = next(
            idx
            for idx, entry in enumerate(entries)
            if entry["module"] == "pam_succeed_if.so" and "breakglass" in " ".join(entry["opts"])
        )
        assert unix < access < pam_time < breakglass < mfa
        control = str(entries[breakglass]["control"])
        assert control.startswith("[") and "success=1" in control

    def test_sudo_requires_sudo_group_before_account_success(self) -> None:
        entries = pam_entries("sudo")
        assert any(entry["module"] == "pam_unix.so" for entry in entries)
        assert any(entry["module"] == "pam_access.so" for entry in entries)
        assert any(entry["module"] == "pam_time.so" for entry in entries)
        group_checks = [
            entry for entry in entries if entry["module"] == "pam_succeed_if.so" and "sudo" in " ".join(entry["opts"])
        ]
        assert group_checks
        assert any(entry["kind"] == "account" for entry in group_checks)
        account_group = next(
            idx
            for idx, entry in enumerate(entries)
            if entry["kind"] == "account"
            and entry["module"] == "pam_succeed_if.so"
            and entry_has_opts(entry, ("user", "ingroup", "sudo"))
        )
        account_unix = next(
            idx
            for idx, entry in enumerate(entries)
            if entry["kind"] == "account" and entry["module"] == "pam_unix.so"
        )
        assert account_group < account_unix

    def test_ci_deploy_is_not_permit_only(self) -> None:
        entries = pam_entries("ci-deploy")
        modules = [entry["module"] for entry in entries]
        assert "pam_permit.so" not in modules
        for module in ("pam_succeed_if.so", "pam_access.so", "pam_time.so", "pam_faillock.so"):
            assert module in modules
        assert any("ci" in " ".join(entry["opts"]) for entry in entries if entry["module"] == "pam_succeed_if.so")

    def test_ci_deploy_root_and_policy_checks_are_ordered(self) -> None:
        entries = pam_entries("ci-deploy")

        def first(kind: str, module: str, required: tuple[str, ...] = ()) -> int:
            return next(
                idx
                for idx, entry in enumerate(entries)
                if entry["kind"] == kind and entry["module"] == module and entry_has_opts(entry, required)
            )

        preauth = first("auth", "pam_faillock.so", ("preauth",))
        root_auth = first("auth", "pam_succeed_if.so", ("user", "!=", "root"))
        ci_auth = first("auth", "pam_succeed_if.so", ("user", "ingroup", "ci"))
        access_auth = first("auth", "pam_access.so")
        time_auth = first("auth", "pam_time.so")
        authfail = first("auth", "pam_faillock.so", ("authfail",))
        authsucc = first("auth", "pam_faillock.so", ("authsucc",))
        assert preauth < root_auth < ci_auth < access_auth < time_auth < authfail < authsucc

        root_account = first("account", "pam_succeed_if.so", ("user", "!=", "root"))
        ci_account = first("account", "pam_succeed_if.so", ("user", "ingroup", "ci"))
        access_account = first("account", "pam_access.so")
        time_account = first("account", "pam_time.so")
        assert root_account < ci_account < access_account < time_account


class TestAccessAndTimePolicy:
    def test_access_first_match_matrix(self) -> None:
        assert access_allows("alice", "10.10.1.20")
        assert not access_allows("erin", "10.10.1.20")
        assert not access_allows("alice", "203.0.113.9")
        assert access_allows("dan", "10.20.8.9")
        assert not access_allows("dan", "10.21.8.9")
        assert access_allows("carol", "10.30.2.44")
        assert not access_allows("carol", "jump01.corp.example")
        assert access_allows("frank", "jump01.corp.example")
        assert not access_allows("frank", "10.30.2.44")
        assert not access_allows("frank", "10.10.2.44")
        assert not access_allows("bob", "198.51.100.4")

    def test_time_first_match_matrix(self) -> None:
        assert time_allows("sshd", "alice", "Mo", 6 * 60)
        assert time_allows("sshd", "alice", "Fr", 21 * 60 + 59)
        assert time_allows("sshd", "alice", "Fr", 16 * 60 + 59)
        assert not time_allows("sshd", "alice", "Fr", 17 * 60)
        assert not time_allows("sshd", "alice", "Fr", 17 * 60 + 59)
        assert time_allows("sshd", "alice", "Fr", 18 * 60)
        assert not time_allows("sshd", "alice", "Fr", 22 * 60)
        assert not time_allows("sshd", "alice", "Sa", 12 * 60)
        assert time_allows("sshd", "frank", "Su", 3 * 60)
        assert time_allows("sshd", "carol", "Tu", 10 * 60)
        assert time_allows("sshd", "carol", "Th", 15 * 60 + 59)
        assert not time_allows("sshd", "carol", "Th", 16 * 60)
        assert not time_allows("sshd", "carol", "We", 11 * 60)
        assert time_allows("ci-deploy", "dan", "We", 12 * 60)
        assert not time_allows("ci-deploy", "dan", "Tu", 3 * 60 + 30)
        assert time_allows("ci-deploy", "dan", "Tu", 4 * 60)
        assert not time_allows("ci-deploy", "dan", "Sa", 12 * 60)
        assert not time_allows("sshd", "dan", "Tu", 11 * 60)
        assert time_allows("sudo", "alice", "Mo", 12 * 60)
        assert not time_allows("sudo", "alice", "Su", 12 * 60)

    def test_combined_auth_outcomes(self) -> None:
        assert group_allowed_by_sshd("alice") and access_allows("alice", "10.10.1.20") and time_allows("sshd", "alice", "Mo", 9 * 60)
        assert not group_allowed_by_sshd("root")
        assert not (access_allows("erin", "10.10.1.20") and time_allows("sshd", "erin", "Mo", 9 * 60))
        assert not (access_allows("alice", "10.10.1.20") and time_allows("sshd", "alice", "Mo", 23 * 60))
        assert not (access_allows("alice", "10.10.1.20") and time_allows("sshd", "alice", "Fr", 17 * 60 + 30))
        assert group_allowed_by_sshd("carol") and access_allows("carol", "10.30.8.9") and time_allows("sshd", "carol", "Tu", 11 * 60)
        assert not (
            group_allowed_by_sshd("carol")
            and access_allows("carol", "10.30.8.9")
            and time_allows("sshd", "carol", "We", 11 * 60)
        )
        assert group_allowed_by_sshd("frank") and access_allows("frank", "jump01.corp.example") and time_allows("sshd", "frank", "Su", 2 * 60)
        assert not (
            group_allowed_by_sshd("frank")
            and access_allows("frank", "10.30.8.9")
            and time_allows("sshd", "frank", "Su", 2 * 60)
        )
        assert access_allows("dan", "10.20.8.9") and time_allows("ci-deploy", "dan", "Tu", 11 * 60)
        assert not (access_allows("dan", "10.20.8.9") and time_allows("ci-deploy", "dan", "Tu", 3 * 60 + 30))
        assert not (
            group_allowed_by_sshd("dan")
            and access_allows("dan", "10.20.8.9")
            and time_allows("sshd", "dan", "Tu", 11 * 60)
        )
        assert not (access_allows("dan", "10.21.8.9") and time_allows("ci-deploy", "dan", "Tu", 11 * 60))
        assert not (access_allows("root", "10.20.8.9") and time_allows("ci-deploy", "root", "Tu", 11 * 60))


class TestSudoers:
    def test_sudoers_has_audited_defaults_and_no_nopasswd(self) -> None:
        text = SUDOERS.read_text(encoding="utf-8")
        lowered = text.lower()
        assert "nopasswd" not in lowered
        for token in ("use_pty", "log_input", "log_output", "timestamp_timeout=0"):
            assert token in text

    def test_sudo_and_breakglass_commands_are_scoped(self) -> None:
        lines = clean_lines(SUDOERS)
        assert any(line.startswith("%sudo ") and "ALL=(ALL:ALL) ALL" in line for line in lines)
        breakglass = [line for line in lines if line.startswith("%breakglass ")]
        assert breakglass
        joined = "\n".join(breakglass)
        assert "/usr/bin/systemctl status *" in joined
        assert "/usr/bin/journalctl *" in joined
        assert "ALL=(ALL:ALL) ALL" not in joined
        commands = joined.split(")", 1)[1]
        allowed = {part.strip() for part in commands.split(",")}
        assert allowed == {"/usr/bin/systemctl status *", "/usr/bin/journalctl *"}
