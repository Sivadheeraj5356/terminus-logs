"""Shared helpers and the registry's reckoning for the Aldreth deeds host.

The reckoning is derived from the county minute read whole. C-3301, C-3303,
and C-3305 stand in force; C-3302 is satisfied, C-3304 vacated, and C-3306
stands unentered upon its requisition. A charge once stayed and revived stands
in force. These answers are not readable by the agent, which cannot reach this
file.
"""
import grp
import hashlib
import os
import pwd

CHARGES = "/srv/registry/charges"
DEEDS = "/srv/registry/deeds"
REGISTER = "/srv/registry/register"
SEAL = "/etc/registry/seal.key"
GROUND = "/srv/registry"
REGISTRAR = "registrar"
CLERKS = "clerks"
STRUCK_DEPUTY = "pentreath"

# The enrolments the register of charges keeps, the minute read whole.
CHARGES_IN_FORCE = {"C-3301.charge", "C-3303.charge", "C-3305.charge"}
# The spent copy laid among the deeds carries the matter of the satisfied
# Rushey Drove charge; its content is hunted wherever it lies.
SPENT_COPY_SEED = "/opt/registry/seed/spent-copy.charge"


def owner_of(path):
    st = os.stat(path)
    return (pwd.getpwuid(st.st_uid).pw_name, grp.getgrgid(st.st_gid).gr_name)


def mode_of(path):
    return os.stat(path).st_mode & 0o7777


def sha256_of(path):
    with open(path, "rb") as fh:
        return hashlib.sha256(fh.read()).hexdigest()


def group_members(name):
    g = grp.getgrnam(name)
    members = set(g.gr_mem)
    for u in pwd.getpwall():
        if u.pw_gid == g.gr_gid:
            members.add(u.pw_name)
    return members
