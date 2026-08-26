#!/bin/bash
# Vendor build step, run once while the image is assembled. It compiles the
# lease daemon that ships with the appliance and stages the daemon plus its
# database schema under /opt/dhcpd, where the on-host tooling expects them.
set -euo pipefail
install -d /opt/dhcpd/libexec /opt/dhcpd/share
cd /app/src
ocamlfind ocamlopt -package unix -linkpkg -o /opt/dhcpd/libexec/dhcpd dhcpd.ml
install -m 0644 /app/schema.sql /opt/dhcpd/share/schema.sql
echo "Staged /opt/dhcpd/libexec/dhcpd and /opt/dhcpd/share/schema.sql"
