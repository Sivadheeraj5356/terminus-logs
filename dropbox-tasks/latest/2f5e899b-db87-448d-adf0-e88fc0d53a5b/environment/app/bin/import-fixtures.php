#!/usr/bin/env php
<?php

declare(strict_types=1);

if ($argc !== 5) {
    fwrite(STDERR, "usage: import-fixtures.php <archive> <host> <port> <credentials.ini>\n");
    exit(2);
}

[$script, $archive, $host, $port, $credentialsPath] = $argv;
$credentials = parse_ini_file($credentialsPath, true, INI_SCANNER_TYPED);
if ($credentials === false || !isset($credentials['ingest'])) {
    throw new RuntimeException('missing ingest credentials');
}

$tmp = sys_get_temp_dir() . '/meter-fixtures-' . getmypid();
if (!mkdir($tmp, 0700, true) && !is_dir($tmp)) {
    throw new RuntimeException('cannot create temporary directory');
}

$phar = new PharData($archive);
$phar->extractTo($tmp, null, true);

$meters = json_decode(file_get_contents($tmp . '/meters.json'), true, 512, JSON_THROW_ON_ERROR);
$tariffs = parse_ini_file($tmp . '/tariffs.ini', true, INI_SCANNER_RAW);
$events = file($tmp . '/events.log', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES);

$redis = new Redis();
$redis->connect($host, (int) $port, 3.0);
$redis->auth([$credentials['ingest']['username'], $credentials['ingest']['password']]);
$redis->select(0);

foreach ($tariffs as $name => $values) {
    $redis->hSet('meter:tariffs', (string) $name, (string) $values['rate']);
}

foreach ($meters['meters'] as $meter) {
    $id = (string) $meter['id'];
    $key = 'meter:device:' . $id;
    $redis->hMSet($key, [
        'site' => (string) $meter['site'],
        'status' => (string) $meter['status'],
        'reading_kwh' => number_format((float) $meter['reading_kwh'], 3, '.', ''),
        'tariff' => (string) $meter['tariff'],
        'updated_at' => (string) $meter['updated_at'],
    ]);
    $redis->sAdd('meter:index', $id);
    $redis->zAdd('meter:ranking:kwh', (float) $meter['reading_kwh'], $id);
}

foreach ($events as $event) {
    $redis->rPush('meter:events', $event);
}

$redis->save();
echo "imported\n";
