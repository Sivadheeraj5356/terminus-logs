<?php
declare(strict_types=1);

namespace EmbedServe;

require_once __DIR__ . '/p01.php';
require_once __DIR__ . '/p02.php';
require_once __DIR__ . '/p03.php';
require_once __DIR__ . '/p04.php';
require_once __DIR__ . '/p05.php';

final class Runner
{
    public static function run(string $profile, string $outPath): array
    {
        $root = '/app/environment';
        $cfg = P03::load($root, $profile);
        $dbPath = P01::pick($root, $cfg);
        $policy = P03::extractPolicy($root, $cfg);
        $denylist = P02::loadStaticDenylist($root, $cfg);
        $audit = P04::scan($root, $cfg, $denylist);
        $report = P05::build($profile, $cfg, $dbPath, $policy, $audit);
        file_put_contents($outPath, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
        return $report;
    }
}
