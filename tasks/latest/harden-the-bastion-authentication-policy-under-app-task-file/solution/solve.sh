#!/bin/bash
set -euo pipefail

ROOT="${1:-/app/task_file}"
if [ ! -d "$ROOT/etc" ]; then
    ROOT="/app/task_file"
fi

cat > "$ROOT/etc/security/faillock.conf" <<'EOF'
deny = 3
fail_interval = 900
unlock_time = 900
even_deny_root
audit
EOF

cat > "$ROOT/etc/ssh/sshd_config" <<'EOF'
UsePAM yes
PasswordAuthentication no
KbdInteractiveAuthentication yes
AuthenticationMethods publickey,keyboard-interactive:pam
PermitRootLogin no
AllowGroups vpn ops breakglass ci
EOF

cat > "$ROOT/etc/security/access.conf" <<'EOF'
-:(contractor):ALL
-:ALL:203.0.113.0/24
+:(breakglass):*.corp.example
-:(breakglass):ALL
+:(vpn):10.10.0.0/16
+:(ops):10.30.0.0/16
+:(ci):10.20.0.0/16
-:ALL:ALL
EOF

cat > "$ROOT/etc/security/time.conf" <<'EOF'
sshd;*;(breakglass);Al0000-2400
sshd;*;(vpn);!Fr1700-1800
sshd;*;(vpn);MoTuWeThFr0600-2200
sshd;*;(ops);TuTh1000-1600
ci-deploy;*;(ci);!Tu0300-0400
ci-deploy;*;(ci);MoTuWeThFr0000-2400
sudo;*;(sudo);!SaSu0000-0000
sudo;*;(sudo);MoTuWeThFr0000-2400
*;*;ALL;!Al0000-2400
EOF

cat > "$ROOT/etc/pam.d/sshd" <<'EOF'
auth required pam_faillock.so preauth silent audit
auth required pam_unix.so try_first_pass
auth required pam_faillock.so authfail audit
auth sufficient pam_faillock.so authsucc audit
auth required pam_access.so accessfile=/app/task_file/etc/security/access.conf
auth required pam_time.so timefile=/app/task_file/etc/security/time.conf
auth [success=1 default=ignore] pam_succeed_if.so quiet user ingroup breakglass
auth required pam_google_authenticator.so nullok
account required pam_unix.so
account required pam_access.so accessfile=/app/task_file/etc/security/access.conf
account required pam_time.so timefile=/app/task_file/etc/security/time.conf
EOF

cat > "$ROOT/etc/pam.d/sudo" <<'EOF'
auth required pam_faillock.so preauth silent audit
auth required pam_unix.so try_first_pass
auth required pam_faillock.so authfail audit
auth sufficient pam_faillock.so authsucc audit
auth requisite pam_succeed_if.so quiet user ingroup sudo
auth required pam_google_authenticator.so
account requisite pam_succeed_if.so quiet user ingroup sudo
account required pam_unix.so
account required pam_access.so accessfile=/app/task_file/etc/security/access.conf
account required pam_time.so timefile=/app/task_file/etc/security/time.conf
EOF

cat > "$ROOT/etc/pam.d/ci-deploy" <<'EOF'
auth required pam_faillock.so preauth silent audit
auth requisite pam_succeed_if.so quiet user != root
auth requisite pam_succeed_if.so quiet user ingroup ci
auth required pam_access.so accessfile=/app/task_file/etc/security/access.conf
auth required pam_time.so timefile=/app/task_file/etc/security/time.conf
auth required pam_faillock.so authfail audit
auth sufficient pam_faillock.so authsucc audit
account requisite pam_succeed_if.so quiet user != root
account requisite pam_succeed_if.so quiet user ingroup ci
account required pam_access.so accessfile=/app/task_file/etc/security/access.conf
account required pam_time.so timefile=/app/task_file/etc/security/time.conf
EOF

cat > "$ROOT/etc/sudoers.d/bastion" <<'EOF'
Defaults use_pty
Defaults log_input
Defaults log_output
Defaults timestamp_timeout=0
%sudo ALL=(ALL:ALL) ALL
%breakglass ALL=(ALL:ALL) /usr/bin/systemctl status *, /usr/bin/journalctl *
EOF
