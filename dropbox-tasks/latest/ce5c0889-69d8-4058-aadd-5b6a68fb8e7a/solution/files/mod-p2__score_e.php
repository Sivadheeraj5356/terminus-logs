<?php
declare(strict_types=1);

function read_lane_moves(string $path): array
{
    $by_round = [];
    if (!is_readable($path)) {
        return $by_round;
    }
    $fh = fopen($path, 'r');
    fgetcsv($fh);
    while (($line = fgetcsv($fh)) !== false) {
        if (($line[0] ?? '') === '') {
            continue;
        }
        $rid = (int) $line[0];
        $by_round[$rid] = [$line[2], $line[3]];
    }
    fclose($fh);
    return $by_round;
}

function score_e(string $db_path, array $verdicts, string $lane_csv): array
{
    $valid = [];
    foreach ($verdicts as $row) {
        if (!empty($row['moves_valid'])) {
            $valid[(int) $row['round_id']] = true;
        }
    }
    $moves = read_lane_moves($lane_csv);
    $pdo = new PDO('sqlite:' . $db_path);
    $rules = $pdo->query('SELECT chain_id, prefix, bonus_pts FROM combo_rules ORDER BY chain_id')
        ->fetchAll(PDO::FETCH_ASSOC);
    $hits = [];
    foreach ($valid as $rid => $_) {
        if (!isset($moves[$rid])) {
            continue;
        }
        [$p1, $p2] = $moves[$rid];
        $pair = $p1 . ',' . $p2;
        foreach ($rules as $rule) {
            if ($rule['prefix'] === $pair) {
                $hits[] = [
                    'round_id' => $rid,
                    'chain_id' => (int) $rule['chain_id'],
                    'bonus_pts' => (int) $rule['bonus_pts'],
                    'matched_prefix' => $rule['prefix'],
                ];
            }
        }
    }
    usort($hits, fn($a, $b) => $a['round_id'] <=> $b['round_id']);
    $total = array_sum(array_column($hits, 'bonus_pts'));
    $rounds = array_values(array_unique(array_column($hits, 'round_id')));
    return [
        'combo_hits' => $hits,
        'combo_total' => $total,
        'rounds_scored' => count($rounds),
    ];
}
