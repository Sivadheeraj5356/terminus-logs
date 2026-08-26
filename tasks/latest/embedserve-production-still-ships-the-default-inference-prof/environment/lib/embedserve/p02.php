<?php
declare(strict_types=1);

namespace EmbedServe;

final class P02
{
    public static function loadStaticDenylist(string $root, array $cfg): array
    {
        $path = (string) $cfg['static_denylist_path'];
        $raw = json_decode((string) file_get_contents($path), true);
        return is_array($raw['crates'] ?? null) ? $raw['crates'] : [];
    }

    public static function componentsForProfile(string $dbPath, string $profile, string $role): array
    {
        $db = new \SQLite3($dbPath);
        $stmt = $db->prepare(
            'SELECT crate_name, version FROM cargo_components WHERE profile_id = :p AND component_role = :r'
        );
        $stmt->bindValue(':p', $profile, SQLITE3_TEXT);
        $stmt->bindValue(':r', $role, SQLITE3_TEXT);
        $res = $stmt->execute();
        $rows = [];
        while ($row = $res->fetchArray(SQLITE3_ASSOC)) {
            $rows[] = $row;
        }
        $db->close();
        return $rows;
    }
}
