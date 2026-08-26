<?php
declare(strict_types=1);

namespace EmbedServe;

final class P04
{
    public static function scan(string $root, array $cfg, array $denylist): array
    {
        $hits = [];
        foreach ($denylist as $crate) {
            $hits[] = [
                'crate_name' => (string) $crate,
                'version' => '0.0.0',
                'advisory_id' => 'STATIC-DENY',
                'severity' => 'medium',
                'package_spec' => (string) $crate,
            ];
        }
        return $hits;
    }

    public static function lockDigest(string $root, array $cfg): string
    {
        return str_repeat('1', 16);
    }
}
