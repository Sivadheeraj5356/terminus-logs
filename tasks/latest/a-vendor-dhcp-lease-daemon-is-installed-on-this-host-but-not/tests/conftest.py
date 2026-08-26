"""Every lease-behaviour test runs against a throwaway state database created
fresh from the shipped schema, so the tests never touch the live service
database at /var/lib/dhcpd/dhcp.db and never interfere with one another. The
provisioning tests inspect the real host state directly and are unaffected by
this fixture."""
import subprocess

import pytest

SCHEMA = "/opt/dhcpd/share/schema.sql"


@pytest.fixture(autouse=True)
def scratch_db(tmp_path, monkeypatch):
    db = str(tmp_path / "scratch.db")
    subprocess.run(["bash", "-c", f"sqlite3 '{db}' < '{SCHEMA}'"], check=True)
    monkeypatch.setenv("DHCPD_DB", db)
    return db
