<?php
declare(strict_types=1);

function policy_h(array $poll, array $policy): array
{
    $fw_a = $poll['fw_q7_a'] ?? '';
    $fw_b = $poll['fw_q7_b'] ?? '';
    return [
        'fw_q7_a' => $fw_a,
        'fw_q7_b' => $fw_b,
        'patch_drift' => 0,
        'policy_limit' => (int) ($policy['max_patch_drift'] ?? 0),
        'policy_excess' => 99,
        'fw_audit_digest' => md5($fw_a . $fw_b),
    ];
}
