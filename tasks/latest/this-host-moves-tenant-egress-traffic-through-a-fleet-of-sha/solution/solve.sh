#!/bin/bash
set -euo pipefail

# Deterministic oracle: bring the services up, write the PHP provisioning
# tool the task asks for, and run it. Everything the tool emits is computed
# from the live API and the raw registry bytes in Redis; nothing is
# hardcoded.

/app/scripts/start-services.sh

mkdir -p /app/bin /app/out

cat > /app/bin/provision-link-rates <<'PHP'
#!/usr/bin/env php
<?php

declare(strict_types=1);

const API_BASE = 'http://127.0.0.1:8080';
const UNIT = 1500;
const BURST_DIVISOR = 5500;
const BURST_MIN = 24;
const RATE_DIVISOR = 40000;

const TIER_BASE = ['background' => 2000, 'general' => 5000, 'express' => 12000];
const TIER_CEIL = ['background' => 3500, 'general' => 8000, 'express' => 18000];

function apiFetch(string $path): array
{
    $raw = file_get_contents(API_BASE . $path);
    if ($raw === false) {
        fwrite(STDERR, "api request failed: {$path}\n");
        exit(1);
    }

    return json_decode($raw, true, 512, JSON_THROW_ON_ERROR);
}

/** Minimal binary-safe RESP client. */
function redisOpen()
{
    $sock = fsockopen('127.0.0.1', 6379, $errno, $errstr, 5.0);
    if ($sock === false) {
        fwrite(STDERR, "redis connect failed: {$errstr}\n");
        exit(1);
    }

    return $sock;
}

function redisCommand($sock, string ...$args)
{
    $wire = '*' . count($args) . "\r\n";
    foreach ($args as $a) {
        $wire .= '$' . strlen($a) . "\r\n" . $a . "\r\n";
    }
    fwrite($sock, $wire);

    return readReply($sock);
}

function readReply($sock)
{
    $line = rtrim(fgets($sock), "\r\n");
    $kind = $line[0];
    $rest = substr($line, 1);
    if ($kind === '+') {
        return $rest;
    }
    if ($kind === ':') {
        return (int) $rest;
    }
    if ($kind === '-') {
        fwrite(STDERR, "redis error: {$rest}\n");
        exit(1);
    }
    if ($kind === '$') {
        $len = (int) $rest;
        if ($len < 0) {
            return null;
        }
        $buf = '';
        while (strlen($buf) < $len + 2) {
            $buf .= fread($sock, $len + 2 - strlen($buf));
        }

        return substr($buf, 0, $len);
    }
    if ($kind === '*') {
        $n = (int) $rest;
        $items = [];
        for ($i = 0; $i < $n; $i++) {
            $items[] = readReply($sock);
        }

        return $items;
    }
    fwrite(STDERR, "unexpected redis reply\n");
    exit(1);
}

/** Parse one LKR1 ledger blob into [detached, dayValues[]]. */
function parseLedger(string $blob): array
{
    if (substr($blob, 0, 4) !== 'LKR1' || ord($blob[4]) !== 1) {
        fwrite(STDERR, "bad ledger header\n");
        exit(1);
    }
    $flags = ord($blob[5]);
    $count = ord($blob[6]) | (ord($blob[7]) << 8);
    $payload = substr($blob, 8, strlen($blob) - 10);
    $sum = 0;
    for ($i = 0, $n = strlen($payload); $i < $n; $i++) {
        $sum = ($sum + ord($payload[$i])) % 65521;
    }
    if (((ord($blob[-2]) << 8) | ord($blob[-1])) !== $sum) {
        fwrite(STDERR, "ledger trailer mismatch\n");
        exit(1);
    }
    $values = [];
    $v = 0;
    for ($i = 0, $n = strlen($payload); $i < $n; $i++) {
        $b = ord($payload[$i]);
        $v = ($v << 7) | ($b & 0x7F);
        if (($b & 0x80) === 0) {
            $values[] = $v;
            $v = 0;
        }
    }
    if (count($values) !== $count) {
        fwrite(STDERR, "ledger varint count mismatch\n");
        exit(1);
    }

    return [($flags & 1) === 1, $values];
}

function applyOps(int $v, array $ops): int
{
    foreach ($ops as $op) {
        if ($op['op'] === 'scale') {
            $v = intdiv($v * $op['num'], $op['den']);
        } elseif ($op['op'] === 'add') {
            $v = $v + $op['k'];
        } elseif ($op['op'] === 'floor') {
            $v = max($v, $op['k']);
        } else {
            fwrite(STDERR, "unknown op\n");
            exit(1);
        }
    }

    return $v;
}

/** Carried-remainder smoothing of the adjusted series. */
function smoothVolumes(array $adjusted): array
{
    $s = [$adjusted[0]];
    $carry = 0;
    $n = count($adjusted);
    for ($d = 1; $d < $n; $d++) {
        $t = 5 * $s[$d - 1] + $adjusted[$d] + $carry;
        $s[] = intdiv($t, 6);
        $carry = $t % 6;
    }

    return $s;
}

/**
 * Little-endian bytes of a GMP value. Native PHP 64-bit multiplication
 * promotes to float and corrupts the fold, so every seal quantity stays in
 * GMP.
 */
function gmpLe(\GMP $v, int $width): string
{
    $out = '';
    for ($i = 0; $i < $width; $i++) {
        $out .= chr(gmp_intval(gmp_and(gmp_div_q($v, gmp_pow(2, 8 * $i)), gmp_init(255))));
    }

    return $out;
}

function main(): void
{
    $mod = gmp_pow(2, 64);
    $prime = gmp_init('1099511628211');

    $links = apiFetch('/links')['links'];
    $meta = [];
    foreach ($links as $link) {
        $meta[$link['iface_id']] = $link;
    }

    $sock = redisOpen();
    $registryOrder = redisCommand($sock, 'LRANGE', 'link:index', '0', '-1');

    $detached = [];
    $smoothed = [];
    $weights = [];
    $rowCount = 0;
    foreach ($registryOrder as $id) {
        $blob = redisCommand($sock, 'GET', 'link:ledger:' . $id);
        [$isDetached, $raws] = parseLedger($blob);
        $ops = apiFetch('/shaping/' . $id)['ops'];
        $adjusted = array_map(fn (int $v): int => applyOps($v, $ops), $raws);
        $smoothed[$id] = smoothVolumes($adjusted);
        $weights[$id] = array_map(
            fn (int $s): int => intdiv($s + UNIT - 1, UNIT),
            $smoothed[$id]
        );
        $detached[$id] = $isDetached;
        $rowCount += count($raws);
    }
    fclose($sock);

    // Seal: fold every ledger row in registry order. The accumulator byte
    // folded at the end of each row is its value as the row's fold began.
    $acc = gmp_init('14695981039346656037');
    $sub = gmp_init(0);
    foreach ($registryOrder as $pos => $id) {
        foreach ($smoothed[$id] as $day => $s) {
            $w = $weights[$id][$day];
            $sub = gmp_mod(gmp_add($sub, gmp_add(gmp_init($s), gmp_init($w))), $mod);
            $snap = $acc;
            $body = gmpLe(gmp_init($pos), 2)
                . gmpLe(gmp_init($day), 2)
                . gmpLe(gmp_init($s), 8)
                . gmpLe($sub, 8)
                . gmpLe($snap, 8);
            for ($i = 0, $n = strlen($body); $i < $n; $i++) {
                $acc = gmp_mod(gmp_mul(gmp_xor($acc, gmp_init(ord($body[$i]))), $prime), $mod);
            }
        }
    }
    $sealHex = str_pad(gmp_strval($acc, 16), 16, '0', STR_PAD_LEFT);

    // Provision the active interfaces in API list order.
    $active = [];
    foreach ($links as $link) {
        $id = $link['iface_id'];
        if ($detached[$id]) {
            continue;
        }
        $peak = max($smoothed[$id]);
        $units = array_sum($weights[$id]);
        $tier = $link['tier'];
        $rate = min(TIER_BASE[$tier] + intdiv($units, RATE_DIVISOR), TIER_CEIL[$tier]);
        $burst = max(intdiv($peak + BURST_DIVISOR - 1, BURST_DIVISOR), BURST_MIN);
        $uid = (int) $link['uid'];
        $stateDir = '/var/lib/link-rate/' . $id;

        if (trim((string) shell_exec('getent group ' . escapeshellarg($id) . ' || true')) === '') {
            run('groupadd -g ' . $uid . ' ' . escapeshellarg($id));
        }
        if (trim((string) shell_exec('getent passwd ' . escapeshellarg($id) . ' || true')) === '') {
            run(
                'useradd -M -u ' . $uid . ' -g ' . $uid
                . ' -d ' . escapeshellarg($stateDir)
                . ' -s /usr/sbin/nologin ' . escapeshellarg($id)
            );
        }
        run('mkdir -p ' . escapeshellarg($stateDir));
        run('chown ' . $uid . ':' . $uid . ' ' . escapeshellarg($stateDir));
        run('chmod 0750 ' . escapeshellarg($stateDir));

        $dropin = "[Match]\n"
            . "Name={$id}\n"
            . "\n"
            . "[TokenBucketFilter]\n"
            . "Parent=root\n"
            . "Rate={$rate}K\n"
            . "BurstBytes={$burst}K\n"
            . "LatencySec=0.05\n";
        writeIfChanged('/etc/systemd/network/40-' . $id . '.network', $dropin);

        $env = "IFACE={$id}\n"
            . "LINK_UID={$uid}\n"
            . "TIER={$tier}\n"
            . "PEAK={$peak}\n"
            . "TOTAL_UNITS={$units}\n"
            . "RATE_KBIT={$rate}\n"
            . "BURST_KIB={$burst}\n";
        writeIfChanged('/etc/link-rate.d/' . $id . '.env', $env);

        $active[$id] = [
            'iface_id' => $id,
            'uid' => $uid,
            'tier' => $tier,
            'peak' => $peak,
            'total_units' => $units,
            'rate_kbit' => $rate,
            'burst_kib' => $burst,
        ];
    }

    ksort($active);
    $detachedIds = array_keys(array_filter($detached));
    sort($detachedIds);

    $manifest = [
        'interfaces' => array_values($active),
        'detached' => $detachedIds,
        'row_count' => $rowCount,
        'seal' => $sealHex,
    ];
    writeIfChanged(
        '/app/out/link-manifest.json',
        json_encode($manifest, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n"
    );
    writeIfChanged('/app/out/seal.hex', $sealHex . "\n");

    echo "provisioned " . count($active) . " interfaces, seal {$sealHex}\n";
}

function run(string $cmd): void
{
    exec($cmd . ' 2>&1', $out, $rc);
    if ($rc !== 0) {
        fwrite(STDERR, "command failed ({$cmd}): " . implode("\n", $out) . "\n");
        exit(1);
    }
}

function writeIfChanged(string $path, string $content): void
{
    if (is_file($path) && file_get_contents($path) === $content) {
        return;
    }
    file_put_contents($path, $content);
}

main();
PHP

chmod +x /app/bin/provision-link-rates

/app/bin/provision-link-rates
