<?php
declare(strict_types=1);

namespace EmbedServe;

final class P01
{
    public static function pick(string $root, array $cfg): string
    {
        $legacy = (string) file_get_contents($root . '/config/legacy_inventory.yaml');
        if (preg_match('/inventory_path:\s*(\S+)/', $legacy, $match)) {
            return $match[1];
        }
        throw new \RuntimeException('legacy inventory path missing');
    }
}
