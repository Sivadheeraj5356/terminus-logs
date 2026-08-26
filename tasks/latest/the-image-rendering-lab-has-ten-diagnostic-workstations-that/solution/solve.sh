#!/usr/bin/env bash
# Oracle solution: author the Rego library required by
# /app/postmortem/postmortem.md and confirm it reproduces every golden plan.
#
# Heredoc-inline authoring: no reads from /tests, no reads from /app/golden.
# The library is derived from the postmortem prose only.
set -euo pipefail

POLICY_DIR="/app/policy"
mkdir -p "${POLICY_DIR}"

cat > "${POLICY_DIR}/workstation.rego" <<'REGO'
# Compliance remediation library for the image-rendering lab diagnostic
# workstations. See /app/postmortem/postmortem.md for the source-of-truth
# decision matrix. This library implements exactly that matrix.
package workstation.plan

import rego.v1

# Section 3: ptrace_scope must be 0.
ptrace_action := ["sysctl:kernel.yama.ptrace_scope=0"] if {
	input.workstation.ptrace_scope != 0
}
ptrace_action := [] if {
	input.workstation.ptrace_scope == 0
}

# Section 4: core_pattern must be the literal "core".
core_pattern_action := ["sysctl:kernel.core_pattern=core"] if {
	input.workstation.core_pattern != "core"
}
core_pattern_action := [] if {
	input.workstation.core_pattern == "core"
}

# Section 5: fs.suid_dumpable must be 2.
suid_dumpable_action := ["sysctl:fs.suid_dumpable=2"] if {
	input.workstation.suid_dumpable != 2
}
suid_dumpable_action := [] if {
	input.workstation.suid_dumpable == 2
}

# Section 6: systemd coredump drop-in must be present.
systemd_action := ["systemd:/etc/systemd/coredump.conf.d/media.conf"] if {
	input.workstation.coredump_conf == false
}
systemd_action := [] if {
	input.workstation.coredump_conf == true
}

# Section 7a: mediauser must be in the debug group.
debug_group_action := ["group:add:mediauser:debug"] if {
	input.workstation.in_debug_group == false
}
debug_group_action := [] if {
	input.workstation.in_debug_group == true
}

# Section 7b: mediauser must be in the media group.
media_group_action := ["group:add:mediauser:media"] if {
	input.workstation.in_media_group == false
}
media_group_action := [] if {
	input.workstation.in_media_group == true
}

# Section 8: RLIMIT_CORE soft AND hard must both be "unlimited".
ulimit_action := ["ulimit:core:unlimited"] if {
	not both_unlimited
}
ulimit_action := [] if {
	both_unlimited
}
both_unlimited if {
	input.workstation.core_soft == "unlimited"
	input.workstation.core_hard == "unlimited"
}

# Section 9a: scratch permission must be 2770 mediauser:media.
scratch_perm_action := ["perms:/var/lib/media/scratch:2770:mediauser:media"] if {
	not scratch_compliant
}
scratch_perm_action := [] if {
	scratch_compliant
}
scratch_compliant if {
	input.workstation.scratch_perms == "2770"
	input.workstation.scratch_owner == "mediauser"
	input.workstation.scratch_group == "media"
}

# Section 9b: immutable attribute must not be set.
scratch_immutable_action := ["fsattr:-i:/var/lib/media/scratch"] if {
	input.workstation.scratch_immutable == true
}
scratch_immutable_action := [] if {
	input.workstation.scratch_immutable == false
}

# Section 9 terminal: fixture-perms is always emitted, keyed off the workload.
fixture_action := [sprintf(
	"fixture-perms:/app/fixtures/%s/sample.%s:0644",
	[input.workstation.workload, input.workstation.workload],
)]

# Section 10: canonical ordering.
actions := array.concat(
	ptrace_action,
	array.concat(
		core_pattern_action,
		array.concat(
			suid_dumpable_action,
			array.concat(
				systemd_action,
				array.concat(
					debug_group_action,
					array.concat(
						media_group_action,
						array.concat(
							ulimit_action,
							array.concat(
								scratch_perm_action,
								array.concat(
									scratch_immutable_action,
									fixture_action,
								),
							),
						),
					),
				),
			),
		),
	),
)
REGO

# Verify every workstation matches its golden.
bash /app/harness/sweep.sh check
