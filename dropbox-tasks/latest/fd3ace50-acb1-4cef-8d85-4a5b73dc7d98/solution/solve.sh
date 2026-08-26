#!/bin/bash
set -euo pipefail

python3 << 'SOLVE_EOF'
import re
import os

src_path = "/app/src/main.cpp"

with open(src_path, "r") as f:
    content = f.read()

original_content = content

# Fix 1: detect_double_tagging - Q-in-Q detection should trigger when inner_tag != outer_tag
old_1 = 'if (flow.ethertype == "0x88A8" && flow.inner_tag == flow.outer_tag) {'
new_1 = 'if (flow.ethertype == "0x88A8" && flow.inner_tag != flow.outer_tag) {'
assert old_1 in content, "Fix 1 target not found: double_tagging Q-in-Q comparison"
content = content.replace(old_1, new_1)

# Fix 2: detect_native_vlan_exploit - should detect when outer_tag equals 1 (native VLAN default)
old_2 = 'if (flow.has_inner_tag && flow.outer_tag != 1) {'
new_2 = 'if (flow.has_inner_tag && flow.outer_tag == 1) {'
assert old_2 in content, "Fix 2 target not found: native_vlan_exploit condition"
content = content.replace(old_2, new_2)

# Fix 3: check_zone_violation - should check blocked_destinations, not allowed_destinations
old_3 = 'for (const auto& allowed : policy.allowed_destinations) {\n        if (allowed == dst_zone) {\n            return true;\n        }\n    }\n    return false;'
new_3 = 'for (const auto& blocked : policy.blocked_destinations) {\n        if (blocked == dst_zone) {\n            return true;\n        }\n    }\n    return false;'
assert old_3 in content, "Fix 3 target not found: zone_violation check"
content = content.replace(old_3, new_3)

# Fix 4: check_acl_violation - should return true on "deny" match, not "permit"
old_4 = '''if (rule.action == "permit") {
                        return true;
                    }
                    return false;'''
new_4 = '''if (rule.action == "deny") {
                        return true;
                    }
                    return false;'''
assert old_4 in content, "Fix 4 target not found: acl_violation permit/deny"
content = content.replace(old_4, new_4)

# Fix 5: check_trunk_misconfigs - DTP check should flag when mode != required
old_5 = 'if (trunk.dtp_mode == required_dtp) {'
new_5 = 'if (trunk.dtp_mode != required_dtp) {'
assert old_5 in content, "Fix 5 target not found: DTP mode comparison"
content = content.replace(old_5, new_5)

# Fix 6: check_native_vlan_consistency - mismatch when VLANs differ, not when equal
old_6 = 'if (endpoints[0].second == endpoints[1].second) {\n                has_mismatch = true;\n                all_consistent = false;'
new_6 = 'if (endpoints[0].second != endpoints[1].second) {\n                has_mismatch = true;\n                all_consistent = false;'
assert old_6 in content, "Fix 6 target not found: native VLAN consistency comparison"
content = content.replace(old_6, new_6)

# Fix 7: build_enforcement_result - risk_level should be critical when mismatch detected
old_7 = '{"risk_level", native_mismatch ? "low" : "critical"}'
new_7 = '{"risk_level", native_mismatch ? "critical" : "low"}'
assert old_7 in content, "Fix 7 target not found: risk_level ternary"
content = content.replace(old_7, new_7)

assert content != original_content, "No changes were applied"

with open(src_path, "w") as f:
    f.write(content)

print("All 7 fixes applied successfully.")
SOLVE_EOF

cd /app && make clean && make
./bin/vlan-segmentation-enforce /app/evidence /app/output

echo "Solution complete. Output at /app/output/enforcement_result.json"
