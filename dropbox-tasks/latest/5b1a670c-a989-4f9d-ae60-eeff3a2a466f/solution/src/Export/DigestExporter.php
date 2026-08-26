<?php

declare(strict_types=1);

namespace IrisProv\Export;

use PDO;

final class DigestExporter
{
    public function export(string $sqlitePath, string $digestPath, string $checksumPath): void
    {
        $pdo = new PDO('sqlite:' . $sqlitePath);
        $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);

        $lines = [];

        $modules = $pdo->query(
            'SELECT module_path, version, checksum_sha256, go_version, is_root
             FROM module_units
             ORDER BY module_path, version'
        )->fetchAll(PDO::FETCH_ASSOC);
        foreach ($modules as $row) {
            $lines[] = $this->compactLine(
                [
                    'kind' => 'module',
                    'module_path' => $row['module_path'],
                    'version' => $row['version'],
                    'checksum_sha256' => $row['checksum_sha256'],
                    'go_version' => $row['go_version'],
                    'is_root' => ((int) $row['is_root']) === 1,
                ]
            );
        }

        $edges = $pdo->query(
            'SELECT parent_path, parent_version, child_path, child_version, edge_kind
             FROM module_edges
             ORDER BY parent_path, parent_version, child_path, child_version, edge_kind'
        )->fetchAll(PDO::FETCH_ASSOC);
        foreach ($edges as $row) {
            $lines[] = $this->compactLine(
                [
                    'kind' => 'edge',
                    'parent_path' => $row['parent_path'],
                    'parent_version' => $row['parent_version'],
                    'child_path' => $row['child_path'],
                    'child_version' => $row['child_version'],
                    'edge_kind' => $row['edge_kind'],
                ]
            );
        }

        $replaces = $pdo->query(
            'SELECT scope_path, scope_version, old_path, old_version, new_path, new_version
             FROM replace_rules
             ORDER BY scope_path, scope_version, old_path, old_version'
        )->fetchAll(PDO::FETCH_ASSOC);
        foreach ($replaces as $row) {
            $lines[] = $this->compactLine(
                [
                    'kind' => 'replace',
                    'scope_path' => $row['scope_path'],
                    'scope_version' => $row['scope_version'],
                    'old_path' => $row['old_path'],
                    'old_version' => $row['old_version'],
                    'new_path' => $row['new_path'],
                    'new_version' => $row['new_version'],
                ]
            );
        }

        sort($lines, SORT_STRING);
        $body = implode("\n", $lines) . "\n";
        file_put_contents($digestPath, $body);
        file_put_contents($checksumPath, hash('sha256', $body) . "\n");
    }

    private function compactLine(array $payload): string
    {
        ksort($payload);

        $encoded = json_encode($payload);
        if ($encoded === false) {
            throw new \RuntimeException('json encode failed');
        }

        return str_replace('\\/', '/', $encoded);
    }
}
