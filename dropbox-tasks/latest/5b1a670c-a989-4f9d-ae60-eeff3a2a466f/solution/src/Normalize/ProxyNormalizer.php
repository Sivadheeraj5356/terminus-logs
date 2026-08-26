<?php

declare(strict_types=1);

namespace IrisProv\Normalize;

final class ProxyNormalizer
{
    public function normalize(string $exportPath, string $pathsConfig): array
    {
        $paths = $this->loadJson($pathsConfig);
        $registerPath = (string) ($paths['cutover_register'] ?? '');
        if ($registerPath === '' || !is_file($registerPath)) {
            throw new \RuntimeException('cutover register missing');
        }
        $register = $this->loadJson($registerPath);
        $replaceFirst = (($register['replace_match_policy'] ?? '') === 'list_scan_alpha');
        $singlePeel = (($register['checksum_peel_mode'] ?? '') === 'single_affix');
        $truthyScaffold = (($register['scaffold_gate'] ?? '') === 'truthy_flags');
        $postRewrite = (($register['queue_timing'] ?? '') === 'post_rewrite');

        $export = $this->loadJson($exportPath);
        $meta = $export['export_meta'] ?? [];
        if (!isset($meta['root_module'], $meta['root_version'])) {
            throw new \RuntimeException('export_meta incomplete');
        }
        $rootModule = (string) $meta['root_module'];
        $rootVersion = $this->stripIncompatible((string) $meta['root_version']);
        $retractQueue = $export['retract_queue'] ?? [];
        $excludeQueue = $export['exclude_queue'] ?? [];
        $moduleIndex = $export['module_index'] ?? [];

        $modules = [];
        $edges = [];
        $replaces = [];
        $replaceSeen = [];
        $visited = [];
        $queue = [[$rootModule, $rootVersion]];

        while ($queue !== []) {
            [$path, $version] = array_shift($queue);
            $visitKey = $path . '@' . $version;
            if (isset($visited[$visitKey])) {
                continue;
            }
            if ($this->isQueued($path, $version, $retractQueue)) {
                continue;
            }
            if ($this->isQueued($path, $version, $excludeQueue)) {
                continue;
            }
            $found = $this->lookupUnit($moduleIndex, $path, $version);
            if ($found === null) {
                continue;
            }
            $visited[$visitKey] = true;
            $unit = $found['unit'];
            $checksum = $this->stripChecksum((string) ($unit['checksum'] ?? ''), $singlePeel);
            $modules[] = [
                'module_path' => $path,
                'version' => $version,
                'checksum_sha256' => $checksum,
                'go_version' => (string) $found['go_version'],
                'is_root' => $path === $rootModule && $version === $rootVersion,
            ];

            $unitReplaces = $unit['replaces'] ?? [];
            foreach ($unit['requires'] ?? [] as $req) {
                if ($this->isScaffold($req, $truthyScaffold)) {
                    continue;
                }
                $reqPath = (string) $req['path'];
                $reqVersion = $this->stripIncompatible((string) $req['version']);

                if (!$postRewrite) {
                    if ($this->isQueued($reqPath, $reqVersion, $retractQueue)) {
                        continue;
                    }
                    if ($this->isQueued($reqPath, $reqVersion, $excludeQueue)) {
                        continue;
                    }
                }

                [$childPath, $childVersion, $edgeKind, $matchedRule] = $this->resolveReplace(
                    $reqPath,
                    $reqVersion,
                    $unitReplaces,
                    $replaceFirst
                );

                if ($postRewrite) {
                    if ($this->isQueued($childPath, $childVersion, $retractQueue)) {
                        continue;
                    }
                    if ($this->isQueued($childPath, $childVersion, $excludeQueue)) {
                        continue;
                    }
                }

                if ($matchedRule !== null) {
                    $ruleKey = implode("\0", [
                        $path,
                        $version,
                        (string) $matchedRule['old_path'],
                        $this->stripIncompatible((string) $matchedRule['old_version']),
                    ]);
                    if (!isset($replaceSeen[$ruleKey])) {
                        $replaceSeen[$ruleKey] = true;
                        $replaces[] = [
                            'scope_path' => $path,
                            'scope_version' => $version,
                            'old_path' => (string) $matchedRule['old_path'],
                            'old_version' => $this->stripIncompatible((string) $matchedRule['old_version']),
                            'new_path' => (string) $matchedRule['new_path'],
                            'new_version' => $this->stripIncompatible((string) $matchedRule['new_version']),
                        ];
                    }
                }
                $edges[] = [
                    'parent_path' => $path,
                    'parent_version' => $version,
                    'child_path' => $childPath,
                    'child_version' => $childVersion,
                    'edge_kind' => $edgeKind,
                ];
                $queue[] = [$childPath, $childVersion];
            }
        }

        usort($modules, static fn (array $a, array $b): int => [$a['module_path'], $a['version']] <=> [$b['module_path'], $b['version']]);
        usort(
            $edges,
            static fn (array $a, array $b): int => [
                $a['parent_path'],
                $a['parent_version'],
                $a['child_path'],
                $a['child_version'],
                $a['edge_kind'],
            ] <=> [
                $b['parent_path'],
                $b['parent_version'],
                $b['child_path'],
                $b['child_version'],
                $b['edge_kind'],
            ]
        );
        usort(
            $replaces,
            static fn (array $a, array $b): int => [
                $a['scope_path'],
                $a['scope_version'],
                $a['old_path'],
                $a['old_version'],
            ] <=> [
                $b['scope_path'],
                $b['scope_version'],
                $b['old_path'],
                $b['old_version'],
            ]
        );

        return [
            'schema_version' => (string) $paths['schema_version'],
            'root_module' => $rootModule,
            'root_version' => $rootVersion,
            'modules' => $modules,
            'edges' => $edges,
            'replace_rules' => $replaces,
        ];
    }

    private function isScaffold(array $req, bool $truthyOnly): bool
    {
        $keys = ['indirect', 'toolchain', 'development', 'test'];
        if ($truthyOnly) {
            foreach ($keys as $key) {
                if (!empty($req[$key])) {
                    return true;
                }
            }

            return false;
        }
        foreach ($keys as $key) {
            if (array_key_exists($key, $req)) {
                return true;
            }
        }

        return false;
    }

    private function stripIncompatible(string $version): string
    {
        if (str_ends_with($version, '+incompatible')) {
            return substr($version, 0, -strlen('+incompatible'));
        }

        return $version;
    }

    private function stripChecksum(string $checksum, bool $singlePeel): string
    {
        if ($singlePeel) {
            foreach (['h1:', 'sha256:'] as $prefix) {
                if (str_starts_with($checksum, $prefix)) {
                    return substr($checksum, strlen($prefix));
                }
            }

            return $checksum;
        }
        $out = $checksum;
        while (true) {
            $changed = false;
            foreach (['h1:', 'sha256:'] as $prefix) {
                if (str_starts_with($out, $prefix)) {
                    $out = substr($out, strlen($prefix));
                    $changed = true;
                    break;
                }
            }
            if (!$changed) {
                break;
            }
        }

        return $out;
    }

    private function isQueued(string $path, string $version, array $queue): bool
    {
        foreach ($queue as $item) {
            if (
                ($item['module_path'] ?? '') === $path
                && $this->stripIncompatible((string) ($item['version'] ?? '')) === $version
            ) {
                return true;
            }
        }

        return false;
    }

    private function resolveReplace(string $childPath, string $childVersion, array $replaces, bool $firstWins): array
    {
        $matched = null;
        $rules = $firstWins ? $replaces : array_reverse($replaces);
        foreach ($rules as $rule) {
            $oldVersion = $this->stripIncompatible((string) $rule['old_version']);
            if (($rule['old_path'] ?? '') === $childPath && $oldVersion === $childVersion) {
                $matched = $rule;
                break;
            }
        }
        if ($matched === null) {
            return [$childPath, $childVersion, 'require', null];
        }

        return [
            (string) $matched['new_path'],
            $this->stripIncompatible((string) $matched['new_version']),
            'replace',
            $matched,
        ];
    }

    private function lookupUnit(array $moduleIndex, string $path, string $version): ?array
    {
        if (!isset($moduleIndex[$path])) {
            return null;
        }
        $versions = $moduleIndex[$path]['versions'] ?? [];
        $want = $this->stripIncompatible($version);
        foreach ($versions as $key => $block) {
            foreach ($block['units'] ?? [] as $unit) {
                if (($unit['path'] ?? '') !== $path) {
                    continue;
                }
                $unitVer = $this->stripIncompatible((string) ($unit['version'] ?? $key));
                if ($unitVer === $want || $this->stripIncompatible((string) $key) === $want) {
                    return [
                        'go_version' => (string) ($block['go_version'] ?? ''),
                        'unit' => $unit,
                    ];
                }
            }
        }

        return null;
    }

    private function loadJson(string $path): array
    {
        if (!is_file($path)) {
            throw new \RuntimeException('missing file ' . $path);
        }
        $raw = file_get_contents($path);
        if ($raw === false) {
            throw new \RuntimeException('read failed ' . $path);
        }
        $doc = json_decode($raw, true);
        if (!is_array($doc)) {
            throw new \RuntimeException('invalid json ' . $path);
        }

        return $doc;
    }
}
