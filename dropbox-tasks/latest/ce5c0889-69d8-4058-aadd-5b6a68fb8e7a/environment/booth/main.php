#!/usr/bin/env php
<?php
declare(strict_types=1);

require_once __DIR__ . '/../mod-h7/op_a.php';
require_once __DIR__ . '/../mod-k9/reconcile_b.php';
require_once __DIR__ . '/../mod-m3/phase_c.php';
require_once __DIR__ . '/../mod-n4/step_d.php';
require_once __DIR__ . '/../mod-p2/score_e.php';
require_once __DIR__ . '/../mod-q1/seal_f.php';
require_once __DIR__ . '/../mod-r8/audit_g.php';
require_once __DIR__ . '/../mod-s2/policy_h.php';

$cmd = $argv[1] ?? 'help';
$out_dir = '/app/output';
@mkdir($out_dir, 0755, true);

if ($cmd === 'ledgers') {
    $merge = op_a([
        'q7_a_csv' => '/app/data/q7_a.csv',
        'q7_b_csv' => '/app/data/q7_b.csv',
    ]);
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-01',
        'q7_a_rows' => $merge['q7_a_rows'],
        'q7_b_rows' => $merge['q7_b_rows'],
        'merged_count' => $merge['merged_count'],
        'dispute_ids' => $merge['dispute_ids'],
        'merged_rounds' => array_map(function ($r) {
            return [
                'round_id' => $r['round_id'],
                'q7_a_winner' => $r['q7_a_winner'],
                'q7_b_winner' => $r['q7_b_winner'],
            ];
        }, $merge['merged_rounds']),
    ];
    file_put_contents($out_dir . '/rival_merge.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'referee') {
    $merge_path = $out_dir . '/rival_merge.json';
    $merge = json_decode(file_get_contents($merge_path), true);
    $poll = phase_c('http://127.0.0.1:7088', $merge['dispute_ids'] ?? []);
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-02',
        'dispute_count' => $poll['dispute_count'],
        'disputes' => $poll['disputes'],
        'fw_q7_a' => $poll['fw_q7_a'],
        'fw_q7_b' => $poll['fw_q7_b'],
    ];
    file_put_contents($out_dir . '/referee_poll.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'verdicts') {
    $merge = json_decode(file_get_contents($out_dir . '/rival_merge.json'), true);
    $poll = json_decode(file_get_contents($out_dir . '/referee_poll.json'), true);
    $rules = reconcile_b('/app/run/move_rules.sqlite', '/app/data/seed_bootstrap.sql');
    $built = step_d($merge, $rules, $poll);
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-03',
        'verdicts' => $built['verdicts'],
        'batch_digest' => $built['batch_digest'],
    ];
    file_put_contents($out_dir . '/verdict_snapshots.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'combos') {
    $verdicts = json_decode(file_get_contents($out_dir . '/verdict_snapshots.json'), true);
    $scored = score_e('/app/run/move_rules.sqlite', $verdicts['verdicts'] ?? [], '/app/data/q7_a.csv');
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-04',
        'combo_hits' => $scored['combo_hits'],
        'combo_total' => $scored['combo_total'],
        'rounds_scored' => $scored['rounds_scored'],
    ];
    file_put_contents($out_dir . '/combo_audit.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'rules') {
    $audit = audit_g(
        '/app/run/move_rules.sqlite',
        '/app/data/q7_a.csv',
        '/app/data/q7_b.csv'
    );
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-06',
        'action_count' => $audit['action_count'],
        'combo_count' => $audit['combo_count'],
        'blocked_count' => $audit['blocked_count'],
        'orphan_round_ids' => $audit['orphan_round_ids'],
        'store_digest' => $audit['store_digest'],
    ];
    file_put_contents($out_dir . '/rules_audit.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'fw') {
    $poll_path = $out_dir . '/referee_poll.json';
    $poll = json_decode(file_get_contents($poll_path), true);
    $policy = json_decode(file_get_contents('/app/config/firmware_policy.json'), true);
    $checked = policy_h($poll, $policy);
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-07',
        'fw_q7_a' => $checked['fw_q7_a'],
        'fw_q7_b' => $checked['fw_q7_b'],
        'patch_drift' => $checked['patch_drift'],
        'policy_limit' => $checked['policy_limit'],
        'policy_excess' => $checked['policy_excess'],
        'fw_audit_digest' => $checked['fw_audit_digest'],
    ];
    file_put_contents($out_dir . '/fw_audit.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

if ($cmd === 'seal') {
    $gate = json_decode(file_get_contents('/app/config/overlay_gate.json'), true);
    $sealed = seal_f(
        $gate,
        $out_dir . '/combo_audit.json',
        '/app/data/q7_overlay.csv'
    );
    $payload = [
        'schema_tag' => 'tb3-pixel-duel-05',
        'overlay_rows' => $sealed['overlay_rows'],
        'overlay_void_ids' => $sealed['overlay_void_ids'],
        'overlay_verdicts' => $sealed['overlay_verdicts'],
        'combo_total' => $sealed['combo_total'],
        'upstream_digest' => $sealed['upstream_digest'],
        'seal_digest' => $sealed['seal_digest'],
    ];
    file_put_contents($out_dir . '/bracket_seal.json', json_encode($payload, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES) . "\n");
    exit(0);
}

fwrite(STDERR, "usage: deskctl ledgers|referee|verdicts|combos|seal|rules|fw\n");
exit(1);
