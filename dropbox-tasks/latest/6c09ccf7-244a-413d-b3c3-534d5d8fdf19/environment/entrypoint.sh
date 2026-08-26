#!/usr/bin/env bash
set -e

# Bring the Aldreth deeds registry up in its drifted state.

groupadd -g 9800 clerks
useradd -u 9801 -r -m -d /home/registrar -s /bin/bash registrar
useradd -u 9802 -m -s /bin/bash tolman
useradd -u 9803 -m -s /bin/bash bazeley
useradd -u 9804 -m -s /bin/bash pentreath
gpasswd -M tolman,bazeley,registrar clerks >/dev/null

PW='$6$aldreth$5Mv1tH4uX8ew6z9tV7it4Ed3a1jJ9uX7lR0yD2hT5fP8zS4pW0zJ7kZ1mC8oD6rL5sK2cF4gM9nO1/'
for u in tolman bazeley pentreath; do usermod -p "$PW" "$u"; done

# the register of charges, as the deputy left it: the satisfied and vacated
# enrolments still standing, and his working memorandum among them
install -d -m 0755 -o root -g root /srv/registry/charges
cp /opt/registry/seed/charges/* /srv/registry/charges/
chown -R root:root /srv/registry/charges
chmod 0644 /srv/registry/charges/*

# the muniment room of deeds, and among them a fair copy of the satisfied
# Rushey Drove charge, laid under a plain leaf
install -d -m 0755 -o root -g root /srv/registry/deeds
cp /opt/registry/seed/deeds/* /srv/registry/deeds/
cp /opt/registry/seed/spent-copy.charge /srv/registry/deeds/deed-0142.deed
chown -R root:root /srv/registry/deeds
chmod 0644 /srv/registry/deeds/*

# the title register, left open as the deputy kept it
cp /opt/registry/seed/register /srv/registry/register
chown root:root /srv/registry/register
chmod 0666 /srv/registry/register

# the registrar's seal, cut fresh for the registry and left in the drawer as the
# deputy kept it, readable and writable under the account
openssl ecparam -name prime256v1 -genkey -noout -out /etc/registry/seal.key 2>/dev/null
chown registrar:registrar /etc/registry/seal.key
chmod 0644 /etc/registry/seal.key

# the registry ground itself, left in the host's default keeping
chown root:root /srv/registry
chmod 0755 /srv/registry

# the struck deputy, still admitted as he was left
install -d -m 0700 -o pentreath -g pentreath /home/pentreath/.ssh
echo 'ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAApentreathdeputyadmissionplaceholder pentreath@aldreth' \
    > /home/pentreath/.ssh/authorized_keys
chown pentreath:pentreath /home/pentreath/.ssh/authorized_keys
chmod 0600 /home/pentreath/.ssh/authorized_keys

exec "$@"
