#!/usr/bin/env php
<?php
declare(strict_types=1);

require_once __DIR__ . '/../lib/embedserve/runner.php';

$opts = getopt('', ['profile:', 'out:']);
$profile = $opts['profile'] ?? '';
$out = $opts['out'] ?? '';
if ($profile === '' || $out === '') {
    fwrite(STDERR, "usage: run_harden_cli.php --profile NAME --out PATH\n");
    exit(2);
}

try {
    EmbedServe\Runner::run($profile, $out);
    exit(0);
} catch (Throwable $ex) {
    fwrite(STDERR, $ex->getMessage() . "\n");
    exit(1);
}
