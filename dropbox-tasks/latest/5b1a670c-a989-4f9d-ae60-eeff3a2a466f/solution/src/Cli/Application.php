<?php

declare(strict_types=1);

namespace IrisProv\Cli;

use IrisProv\Export\DigestExporter;
use IrisProv\Load\GraphLoader;
use IrisProv\Normalize\ProxyNormalizer;
use IrisProv\Support\JsonWriter;

final class Application
{
    public function run(array $argv): int
    {
        $cmd = $argv[1] ?? '';
        if ($cmd === 'normalize') {
            return $this->runNormalize(array_slice($argv, 2));
        }
        if ($cmd === 'migrate') {
            return $this->runMigrate(array_slice($argv, 2));
        }
        if ($cmd === 'export-digest') {
            return $this->runExport(array_slice($argv, 2));
        }
        fwrite(STDERR, "unknown command\n");
        return 1;
    }

    private function runNormalize(array $args): int
    {
        $parsed = $this->parseFlags($args, ['export', 'paths', 'out']);
        if ($parsed === null) {
            fwrite(STDERR, "missing normalize flags\n");
            return 1;
        }
        if (!is_file($parsed['export'])) {
            fwrite(STDERR, "export not found\n");
            return 1;
        }
        $normalizer = new ProxyNormalizer();
        try {
            $doc = $normalizer->normalize($parsed['export'], $parsed['paths']);
        } catch (\RuntimeException $e) {
            if ($e->getMessage() === 'export_meta incomplete') {
                fwrite(STDERR, "export_meta incomplete\n");
                return 1;
            }
            throw $e;
        }
        JsonWriter::writePretty($parsed['out'], $doc);
        return 0;
    }

    private function runMigrate(array $args): int
    {
        $parsed = $this->parseFlags($args, ['graph', 'paths']);
        if ($parsed === null) {
            fwrite(STDERR, "missing migrate flags\n");
            return 1;
        }
        if (!is_file($parsed['graph'])) {
            fwrite(STDERR, "graph not found\n");
            return 1;
        }
        $paths = $this->loadJson($parsed['paths']);
        $graph = $this->loadJson($parsed['graph']);
        $sqlite = (string) $paths['sqlite_path'];
        $dir = dirname($sqlite);
        if (!is_dir($dir)) {
            mkdir($dir, 0777, true);
        }
        if (is_file($sqlite)) {
            unlink($sqlite);
        }
        $legacy = preg_replace('/\.sqlite3$/', '.sqlite', $sqlite);
        if ($legacy !== $sqlite && is_file($legacy)) {
            unlink($legacy);
        }
        $phinxName = (string) preg_replace('/\.sqlite3$/', '', $sqlite);
        $configPath = sys_get_temp_dir() . '/iris-phinx-' . getmypid() . '.php';
        $configBody = "<?php\nreturn [\n"
            . "    'paths' => ['migrations' => '/workspace/iris-provenance/db/migrations'],\n"
            . "    'environments' => [\n"
            . "        'default_migration_table' => 'phinxlog',\n"
            . "        'default_environment' => 'workspace',\n"
            . "        'workspace' => [\n"
            . "            'adapter' => 'sqlite',\n"
            . "            'name' => " . var_export($phinxName, true) . ",\n"
            . "        ],\n"
            . "    ],\n"
            . "    'version_order' => 'creation',\n"
            . "];\n";
        file_put_contents($configPath, $configBody);
        $phinx = '/workspace/iris-provenance/vendor/bin/phinx';
        $prev = getcwd();
        chdir('/workspace/iris-provenance');
        $cmd = sprintf(
            '%s migrate -c %s -e workspace 2>&1',
            escapeshellarg($phinx),
            escapeshellarg($configPath)
        );
        exec($cmd, $output, $code);
        if ($prev !== false) {
            chdir($prev);
        }
        @unlink($configPath);
        if ($code !== 0) {
            fwrite(STDERR, implode("\n", $output) . "\n");
            return 1;
        }
        $loader = new GraphLoader();
        $loader->load($sqlite, $graph);
        return 0;
    }

    private function runExport(array $args): int
    {
        $parsed = $this->parseFlags($args, ['paths']);
        if ($parsed === null) {
            fwrite(STDERR, "paths config missing\n");
            return 1;
        }
        if (!is_file($parsed['paths'])) {
            fwrite(STDERR, "paths config missing\n");
            return 1;
        }
        $cfg = $this->loadJson($parsed['paths']);
        $sqlite = (string) $cfg['sqlite_path'];
        if (!is_file($sqlite)) {
            fwrite(STDERR, "sqlite database missing\n");
            return 1;
        }
        $exporter = new DigestExporter();
        $exporter->export(
            $sqlite,
            (string) $cfg['digest_path'],
            (string) $cfg['checksum_path']
        );
        return 0;
    }

    private function parseFlags(array $args, array $keys): ?array
    {
        $out = [];
        for ($i = 0; $i < count($args); $i++) {
            foreach ($keys as $key) {
                $flag = '--' . $key;
                if ($args[$i] === $flag && isset($args[$i + 1])) {
                    $out[$key] = $args[$i + 1];
                    $i++;
                }
            }
        }
        foreach ($keys as $key) {
            if (!isset($out[$key])) {
                return null;
            }
        }

        return $out;
    }

    private function loadJson(string $path): array
    {
        $raw = file_get_contents($path);
        if ($raw === false) {
            throw new \RuntimeException('read failed');
        }
        $doc = json_decode($raw, true);
        if (!is_array($doc)) {
            throw new \RuntimeException('invalid json');
        }

        return $doc;
    }
}
