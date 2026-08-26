<?php
declare(strict_types=1);

namespace EmbedServe;

final class P05
{
    public static function build(
        string $profile,
        array $cfg,
        string $dbPath,
        array $policy,
        array $auditHits
    ): array {
        $disabled = [];
        foreach ($auditHits as $hit) {
            $disabled[] = [
                'crate_name' => $hit['crate_name'],
                'version' => $hit['version'],
                'advisory_id' => $hit['advisory_id'],
            ];
        }
        usort($disabled, static fn(array $a, array $b): int => strcmp($a['crate_name'], $b['crate_name']));

        $defaults = [];
        foreach ($policy as $key => $value) {
            $defaults[] = ['setting_key' => $key, 'value' => $value];
        }
        usort($defaults, static fn(array $a, array $b): int => strcmp($a['setting_key'], $b['setting_key']));

        return [
            'api_version' => '2025-07',
            'profile' => $profile,
            'opened_db_basename' => basename($dbPath),
            'ops_section' => 4,
            'ops_digest' => P03::sectionDigest('/app/environment', $cfg),
            'lock_digest' => P04::lockDigest('/app/environment', $cfg),
            'disabled_components' => $disabled,
            'inference_defaults_applied' => $defaults,
            'advisory_evidence_count' => count($auditHits),
            'sql_evidence' => [
                'inventory_path' => $dbPath,
                'components_disabled' => 0,
                'defaults_changed' => 0,
            ],
        ];
    }
}
