<?php

declare(strict_types=1);

namespace IrisProv\Load;

use PDO;

final class GraphLoader
{
    public function load(string $sqlitePath, array $graph): void
    {
        $pdo = new PDO('sqlite:' . $sqlitePath);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        foreach ($graph['modules'] as $row) {
            $stmt = $pdo->prepare(
                'INSERT INTO module_units (module_path, version, checksum_sha256, go_version, is_root)
                 VALUES (:module_path, :version, :checksum_sha256, :go_version, :is_root)'
            );
            $stmt->execute([
                'module_path' => $row['module_path'],
                'version' => $row['version'],
                'checksum_sha256' => $row['checksum_sha256'],
                'go_version' => $row['go_version'],
                'is_root' => $row['is_root'] ? 1 : 0,
            ]);
        }

        foreach ($graph['edges'] as $row) {
            $stmt = $pdo->prepare(
                'INSERT INTO module_edges (parent_path, parent_version, child_path, child_version, edge_kind)
                 VALUES (:parent_path, :parent_version, :child_path, :child_version, :edge_kind)'
            );
            $stmt->execute([
                'parent_path' => $row['parent_path'],
                'parent_version' => $row['parent_version'],
                'child_path' => $row['child_path'],
                'child_version' => $row['child_version'],
                'edge_kind' => $row['edge_kind'],
            ]);
        }

        foreach ($graph['replace_rules'] as $row) {
            $stmt = $pdo->prepare(
                'INSERT INTO replace_rules (scope_path, scope_version, old_path, old_version, new_path, new_version)
                 VALUES (:scope_path, :scope_version, :old_path, :old_version, :new_path, :new_version)'
            );
            $stmt->execute([
                'scope_path' => $row['scope_path'],
                'scope_version' => $row['scope_version'],
                'old_path' => $row['old_path'],
                'old_version' => $row['old_version'],
                'new_path' => $row['new_path'],
                'new_version' => $row['new_version'],
            ]);
        }
    }
}
