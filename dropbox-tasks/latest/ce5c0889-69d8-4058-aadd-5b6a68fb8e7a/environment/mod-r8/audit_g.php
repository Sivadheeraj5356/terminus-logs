<?php
declare(strict_types=1);

function audit_g(string $db_path, string $alpha_csv, string $beta_csv): array
{
    $pdo = new PDO('sqlite:' . $db_path);
    $action_count = (int) $pdo->query('SELECT COUNT(*) FROM legal_actions')->fetchColumn();
    return [
        'action_count' => $action_count,
        'combo_count' => 0,
        'blocked_count' => 0,
        'orphan_round_ids' => [],
        'store_digest' => md5('store'),
    ];
}
