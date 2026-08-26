<?php
declare(strict_types=1);

function reconcile_b(string $db_path, string $seed_sql): array
{
    if (file_exists($db_path)) {
        unlink($db_path);
    }
    $pdo = new PDO('sqlite:' . $db_path);
    $pdo->exec(file_get_contents($seed_sql));
    $action_count = (int) $pdo->query('SELECT COUNT(*) FROM legal_actions')->fetchColumn();
    $combo_count = 0;
    $blocked_count = 0;
    $legal = [];
    $stmt = $pdo->query('SELECT round_id, seq, action_token FROM legal_actions ORDER BY round_id, seq');
    while ($row = $stmt->fetch(PDO::FETCH_ASSOC)) {
        $rid = (int) $row['round_id'];
        if (!isset($legal[$rid])) {
            $legal[$rid] = [];
        }
        $legal[$rid][(int) $row['seq']] = $row['action_token'];
    }
    return [
        'action_count' => $action_count,
        'combo_count' => $combo_count,
        'blocked_count' => $blocked_count,
        'legal_by_round' => $legal,
        'blocked' => [],
    ];
}
