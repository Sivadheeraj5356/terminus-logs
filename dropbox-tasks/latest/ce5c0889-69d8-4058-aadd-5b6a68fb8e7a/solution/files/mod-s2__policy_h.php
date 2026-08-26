<?php
declare(strict_types=1);

function semver_patch_drift(string $left, string $right): int
{
    $a = array_map('intval', explode('.', $left));
    $b = array_map('intval', explode('.', $right));
    if (count($a) < 3 || count($b) < 3) {
        return 100;
    }
    if ($a[0] !== $b[0] || $a[1] !== $b[1]) {
        return 100;
    }
    return abs($a[2] - $b[2]);
}

function policy_h(array $poll, array $policy): array
{
    $fw_a = $poll['fw_q7_a'] ?? '';
    $fw_b = $poll['fw_q7_b'] ?? '';
    $patch_drift = semver_patch_drift($fw_a, $fw_b);
    $policy_limit = (int) ($policy['max_patch_drift'] ?? 0);
    $policy_excess = max(0, $patch_drift - $policy_limit);
    $digest_payload = [
        'fw_q7_a' => $fw_a,
        'fw_q7_b' => $fw_b,
        'patch_drift' => $patch_drift,
        'policy_excess' => $policy_excess,
    ];
    ksort($digest_payload);
    $fw_audit_digest = hash('sha256', json_encode($digest_payload, JSON_UNESCAPED_SLASHES));
    return [
        'fw_q7_a' => $fw_a,
        'fw_q7_b' => $fw_b,
        'patch_drift' => $patch_drift,
        'policy_limit' => $policy_limit,
        'policy_excess' => $policy_excess,
        'fw_audit_digest' => $fw_audit_digest,
    ];
}
