#!/usr/bin/env bash
set -euo pipefail

# The Aldreth registry is brought to the state the standing orders and the
# county minute, read whole, require. The charges in force are C-3301, C-3303,
# and C-3305; C-3302 is satisfied, C-3304 vacated, C-3306 unentered upon its
# requisition. A charge once stayed and revived stands in force.

# Part 2: the register of charges holds exactly the enrolments of the charges in
# force and nothing besides. Keep only those enrolments, giving up every other
# file by rule, the satisfied and vacated enrolments and any memorandum or matter
# that is not an enrolment of a charge in force.
keep_charges="C-3301.charge C-3303.charge C-3305.charge"
for f in /srv/registry/charges/*; do
    [ -e "$f" ] || continue
    name="$(basename "$f")"
    keep=no
    for k in $keep_charges; do
        [ "$name" = "$k" ] && keep=yes
    done
    [ "$keep" = yes ] || rm -f "$f"
done

# Part 2: no copy of a charge put an end to survives anywhere under the registry,
# among the deeds no less than elsewhere; give up every copy carrying the matter
# of the satisfied Rushey Drove charge, matched by content and not by leaf.
spent="$(sha256sum /opt/registry/seed/spent-copy.charge | cut -d' ' -f1)"
while IFS= read -r -d '' p; do
    if [ "$(sha256sum "$p" | cut -d' ' -f1)" = "$spent" ]; then
        rm -f "$p"
    fi
done < <(find /srv/registry -xdev -type f -print0)

# Part 4: the registrar's seal is held to the registrar's reading alone, read to
# seal and written by no hand.
chown registrar:registrar /etc/registry/seal.key
chmod 0400 /etc/registry/seal.key

# Part 3: the register of titles is the registry's made record, kept to the
# registry and closed to the wider host.
chown registrar:clerks /srv/registry/register
chmod 0640 /srv/registry/register

# Part 5: the struck deputy is put off the registry in full, his account kept.
usermod -s /usr/sbin/nologin pentreath
usermod -L pentreath
rm -f /home/pentreath/.ssh/authorized_keys /home/pentreath/.ssh/authorized_keys2

# Part 5: the registry ground is the county's own, closed to the wider host,
# settled last after every hand has done its work.
chown -R registrar:clerks /srv/registry/charges /srv/registry/deeds
chown registrar:clerks /srv/registry
chmod 0750 /srv/registry
