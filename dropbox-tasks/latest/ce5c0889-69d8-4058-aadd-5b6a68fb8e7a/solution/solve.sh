#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

install -D -m 0644 "${ROOT_DIR}/files/mod-h7__op_a.php" /app/mod-h7/op_a.php
install -D -m 0644 "${ROOT_DIR}/files/mod-m3__phase_c.php" /app/mod-m3/phase_c.php
install -D -m 0644 "${ROOT_DIR}/files/mod-k9__reconcile_b.php" /app/mod-k9/reconcile_b.php
install -D -m 0644 "${ROOT_DIR}/files/mod-n4__step_d.php" /app/mod-n4/step_d.php
install -D -m 0644 "${ROOT_DIR}/files/mod-p2__score_e.php" /app/mod-p2/score_e.php
install -D -m 0644 "${ROOT_DIR}/files/mod-q1__seal_f.php" /app/mod-q1/seal_f.php
install -D -m 0644 "${ROOT_DIR}/files/mod-r8__audit_g.php" /app/mod-r8/audit_g.php
install -D -m 0644 "${ROOT_DIR}/files/mod-s2__policy_h.php" /app/mod-s2/policy_h.php
install -D -m 0755 "${ROOT_DIR}/files/scripts__desk_init.sh" /app/scripts/desk_init.sh

php -l /app/mod-h7/op_a.php
php -l /app/mod-k9/reconcile_b.php
php -l /app/mod-m3/phase_c.php
php -l /app/mod-n4/step_d.php
php -l /app/mod-p2/score_e.php
php -l /app/mod-q1/seal_f.php
php -l /app/mod-r8/audit_g.php
php -l /app/mod-s2/policy_h.php
test -x /app/scripts/desk_init.sh
test -f /app/booth/main.php

bash /app/scripts/desk_init.sh
bash /app/scripts/build_all.sh
bash /app/scripts/ref_svc_start.sh

bash /app/scripts/milestone_probes.sh ledgers
bash /app/scripts/milestone_probes.sh referee
bash /app/scripts/milestone_probes.sh verdicts
bash /app/scripts/milestone_probes.sh combos
bash /app/scripts/milestone_probes.sh seal
bash /app/scripts/milestone_probes.sh rules
bash /app/scripts/milestone_probes.sh fw
