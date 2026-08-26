#!/usr/bin/env bash
set -euo pipefail

cat > /app/environment/lib/embedserve/p01.php <<'PHP'
<?php
declare(strict_types=1);

namespace EmbedServe;

final class P01
{
    public static function pick(string $root, array $cfg): string
    {
        return (string) $cfg['inventory_path'];
    }
}
PHP

cat > /app/environment/lib/embedserve/p03.php <<'PHP'
<?php
declare(strict_types=1);

namespace EmbedServe;

final class P03
{
    public static function load(string $root, string $profile): array
    {
        $all = json_decode((string) file_get_contents($root . '/config/profiles.json'), true);
        if (!isset($all[$profile])) {
            throw new \RuntimeException("unknown profile: {$profile}");
        }
        return $all[$profile];
    }

    public static function sectionBody(string $bundlePath, int $section): string
    {
        $body = (string) file_get_contents($bundlePath);
        $pattern = '/## Section ' . $section . '[\s\S]*?(?=\n## )/';
        if (!preg_match($pattern, $body, $match)) {
            throw new \RuntimeException("section {$section} missing");
        }
        return $match[0];
    }

    public static function extractPolicy(string $root, array $cfg): array
    {
        $section = self::sectionBody((string) $cfg['ops_bundle_path'], (int) $cfg['ops_section']);
        $pattern = '/A-2025-07[\s\S]*?ratification_status \*\*ratified\*\*; '
            . 'model_sandbox_enabled \*\*(\w+)\*\*; '
            . 'allow_local_weight_files \*\*(\w+)\*\*; '
            . 'mmap_model_weights \*\*(\w+)\*\*; '
            . 'tokenizer_remote_code \*\*(\w+)\*\*; '
            . 'tokenizer_trust_remote_code \*\*(\w+)\*\*/';
        if (!preg_match($pattern, $section, $match)) {
            throw new \RuntimeException('ratified amendment row missing');
        }
        $keys = [
            'model_sandbox_enabled',
            'allow_local_weight_files',
            'mmap_model_weights',
            'tokenizer_remote_code',
            'tokenizer_trust_remote_code',
        ];
        $policy = [];
        foreach ($keys as $idx => $key) {
            $policy[$key] = $match[$idx + 1];
        }
        return $policy;
    }

    public static function sectionDigest(string $root, array $cfg): string
    {
        $section = self::sectionBody((string) $cfg['ops_bundle_path'], (int) $cfg['ops_section']);
        return substr(hash('sha256', $section), 0, 16);
    }
}
PHP

cat > /app/environment/lib/embedserve/p04.php <<'PHP'
<?php
declare(strict_types=1);

namespace EmbedServe;

final class P04
{
    public static function scan(string $root, array $cfg, array $inventoryCrates): array
    {
        $cmd = sprintf(
            'cd %s && cargo audit --json --db %s --file Cargo.lock -n 2>/dev/null',
            escapeshellarg(dirname((string) $cfg['manifest_path'])),
            escapeshellarg((string) $cfg['advisory_db_path'])
        );
        $raw = shell_exec($cmd);
        if ($raw === null || $raw === '') {
            throw new \RuntimeException('cargo audit produced no output');
        }
        $payload = json_decode($raw, true);
        if (!is_array($payload)) {
            throw new \RuntimeException('cargo audit json invalid');
        }
        $hits = [];
        foreach ($payload['vulnerabilities']['list'] ?? [] as $item) {
            $advisory = $item['advisory'] ?? [];
            $crate = (string) ($advisory['package'] ?? '');
            if ($crate === '' || !isset($inventoryCrates[$crate])) {
                continue;
            }
            $hits[] = [
                'crate_name' => $crate,
                'version' => $inventoryCrates[$crate],
                'advisory_id' => (string) ($advisory['id'] ?? ''),
                'severity' => (string) ($item['severity'] ?? $advisory['severity'] ?? 'medium'),
                'package_spec' => sprintf(
                    '%s (%s)',
                    $advisory['package'] ?? '',
                    $inventoryCrates[$crate] ?? ''
                ),
            ];
        }
        usort($hits, static fn(array $a, array $b): int => strcmp($a['crate_name'], $b['crate_name']));
        return $hits;
    }

    public static function lockDigest(string $root, array $cfg): string
    {
        $bytes = (string) file_get_contents((string) $cfg['lockfile_path']);
        return substr(hash('sha256', $bytes), 0, 16);
    }
}
PHP

cat > /app/environment/lib/embedserve/p02.php <<'PHP'
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
            $rows[$row['crate_name']] = $row['version'];
        }
        $db->close();
        return $rows;
    }
}
PHP

cat > /app/environment/lib/embedserve/p05.php <<'PHP'
<?php
declare(strict_types=1);

namespace EmbedServe;

final class P05
{
    public static function deterministicTimestamp(string $opsDigest, string $lockDigest): string
    {
        $stamp = substr(hash('sha256', $opsDigest . ':' . $lockDigest), 0, 8);
        $offset = hexdec($stamp) % 86400;
        $minute = intdiv($offset, 60) % 60;
        $second = $offset % 60;
        return sprintf('2025-07-01T00:%02d:%02dZ', $minute, $second);
    }

    public static function build(
        string $profile,
        array $cfg,
        string $dbPath,
        array $policy,
        array $auditHits
    ): array {
        $opsDigest = P03::sectionDigest('/app/environment', $cfg);
        $lockDigest = P04::lockDigest('/app/environment', $cfg);
        $runId = 'hard-' . substr(hash('sha256', $opsDigest . $lockDigest), 0, 12);
        $recordedAt = self::deterministicTimestamp($opsDigest, $lockDigest);

        $db = new \SQLite3($dbPath);
        $db->exec('BEGIN');
        try {
            foreach ($auditHits as $hit) {
                $stmt = $db->prepare(
                    'UPDATE cargo_components SET enabled = 0, advisory_id = :aid, disabled_reason = :reason '
                    . 'WHERE profile_id = :p AND crate_name = :c'
                );
                $stmt->bindValue(':aid', $hit['advisory_id'], SQLITE3_TEXT);
                $stmt->bindValue(':reason', 'advisory:' . $hit['advisory_id'], SQLITE3_TEXT);
                $stmt->bindValue(':p', $profile, SQLITE3_TEXT);
                $stmt->bindValue(':c', $hit['crate_name'], SQLITE3_TEXT);
                $stmt->execute();

                $ins = $db->prepare(
                    'INSERT OR REPLACE INTO advisory_evidence '
                    . '(profile_id, advisory_id, crate_name, severity, package_spec, recorded_at, audit_run_id) '
                    . 'VALUES (:p, :aid, :c, :sev, :spec, :at, :rid)'
                );
                $ins->bindValue(':p', $profile, SQLITE3_TEXT);
                $ins->bindValue(':aid', $hit['advisory_id'], SQLITE3_TEXT);
                $ins->bindValue(':c', $hit['crate_name'], SQLITE3_TEXT);
                $ins->bindValue(':sev', $hit['severity'], SQLITE3_TEXT);
                $ins->bindValue(':spec', $hit['package_spec'], SQLITE3_TEXT);
                $ins->bindValue(':at', $recordedAt, SQLITE3_TEXT);
                $ins->bindValue(':rid', $runId, SQLITE3_TEXT);
                $ins->execute();
            }

            foreach ($policy as $key => $value) {
                $stmt = $db->prepare(
                    'UPDATE inference_defaults SET current_value = :val, applied = 1 '
                    . 'WHERE profile_id = :p AND setting_key = :k'
                );
                $stmt->bindValue(':val', $value, SQLITE3_TEXT);
                $stmt->bindValue(':p', $profile, SQLITE3_TEXT);
                $stmt->bindValue(':k', $key, SQLITE3_TEXT);
                $stmt->execute();
            }

            $run = $db->prepare(
                'INSERT OR REPLACE INTO harden_runs '
                . '(run_id, profile_id, ops_digest, lock_digest, advisory_count, completed_at) '
                . 'VALUES (:rid, :p, :ops, :lock, :cnt, :at)'
            );
            $run->bindValue(':rid', $runId, SQLITE3_TEXT);
            $run->bindValue(':p', $profile, SQLITE3_TEXT);
            $run->bindValue(':ops', $opsDigest, SQLITE3_TEXT);
            $run->bindValue(':lock', $lockDigest, SQLITE3_TEXT);
            $run->bindValue(':cnt', count($auditHits), SQLITE3_INTEGER);
            $run->bindValue(':at', $recordedAt, SQLITE3_TEXT);
            $run->execute();
            $db->exec('COMMIT');
        } catch (\Throwable $ex) {
            $db->exec('ROLLBACK');
            throw $ex;
        } finally {
            $db->close();
        }

        $disabled = array_map(static fn(array $hit): array => [
            'crate_name' => $hit['crate_name'],
            'version' => $hit['version'],
            'advisory_id' => $hit['advisory_id'],
        ], $auditHits);

        $defaults = [];
        foreach ($policy as $key => $value) {
            $defaults[] = ['setting_key' => $key, 'value' => $value];
        }
        usort($defaults, static fn(array $a, array $b): int => strcmp($a['setting_key'], $b['setting_key']));

        return [
            'api_version' => (string) $cfg['api_version'],
            'profile' => $profile,
            'opened_db_basename' => basename($dbPath),
            'ops_section' => (int) $cfg['ops_section'],
            'ops_digest' => $opsDigest,
            'lock_digest' => $lockDigest,
            'disabled_components' => $disabled,
            'inference_defaults_applied' => $defaults,
            'advisory_evidence_count' => count($auditHits),
            'sql_evidence' => [
                'inventory_path' => $dbPath,
                'components_disabled' => count($auditHits),
                'defaults_changed' => count($policy),
            ],
        ];
    }
}
PHP

cat > /app/environment/lib/embedserve/runner.php <<'PHP'
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
        $inventory = P02::componentsForProfile($dbPath, $profile, (string) $cfg['sidecar_role']);
        $audit = P04::scan($root, $cfg, $inventory);
        $report = P05::build($profile, $cfg, $dbPath, $policy, $audit);
        file_put_contents($outPath, json_encode($report, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
        return $report;
    }
}
PHP

mkdir -p /app/out
php /app/environment/scripts/run_harden_cli.php \
  --profile embedserve-default \
  --out /app/out/harden_report.json
