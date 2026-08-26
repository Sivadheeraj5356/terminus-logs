<?php
declare(strict_types=1);

function round_ids_from_csv(string $path): array
{
    $ids = [];
    if (!is_readable($path)) {
        return $ids;
    }
    $fh = fopen($path, 'r');
    fgetcsv($fh);
    while (($line = fgetcsv($fh)) !== false) {
        if (($line[0] ?? '') === '') {
            continue;
        }
        $ids[] = (int) $line[0];
    }
    fclose($fh);
    return $ids;
}

function audit_g(string $db_path, string $alpha_csv, string $beta_csv): array
{
    $pdo = new PDO('sqlite:' . $db_path);
    $action_count = (int) $pdo->query('SELECT COUNT(*) FROM legal_actions')->fetchColumn();
    $combo_count = (int) $pdo->query('SELECT COUNT(*) FROM combo_rules')->fetchColumn();
    $blocked_count = (int) $pdo->query('SELECT COUNT(*) FROM blocked_actions')->fetchColumn();
    $ledger_ids = array_unique(array_merge(
        round_ids_from_csv($alpha_csv),
        round_ids_from_csv($beta_csv)
    ));
    $orphan_round_ids = [];
    $stmt = $pdo->query('SELECT DISTINCT round_id FROM legal_actions ORDER BY round_id');
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $rid = (int) $row['round_id'];
        if (!in_array($rid, $ledger_ids, true)) {
            $orphan_round_ids[] = $rid;
        }
    }
    $digest_payload = [
        'action_count' => $action_count,
        'blocked_count' => $blocked_count,
        'combo_count' => $combo_count,
        'orphan_round_ids' => $orphan_round_ids,
    ];
    ksort($digest_payload);
    $store_digest = hash('sha256', json_encode($digest_payload, JSON_UNESCAPED_SLASHES));
    return [
        'action_count' => $action_count,
        'combo_count' => $combo_count,
        'blocked_count' => $blocked_count,
        'orphan_round_ids' => $orphan_round_ids,
        'store_digest' => $store_digest,
    ];
}
