<?php
declare(strict_types=1);

function ledger_moves_valid(int $round_id, string $p1, string $p2, array $rules): bool
{
    $legal = $rules['legal_by_round'][$round_id] ?? null;
    if ($legal === null) {
        return false;
    }
    if (($legal[1] ?? '') !== $p1 || ($legal[2] ?? '') !== $p2) {
        return false;
    }
    if (isset($rules['blocked'][$p1]) || isset($rules['blocked'][$p2])) {
        return false;
    }
    return true;
}

function sorted_verdicts_json(array $verdicts): string
{
    $normalized = [];
    foreach ($verdicts as $v) {
        $row = $v;
        ksort($row);
        $normalized[] = $row;
    }
    return json_encode($normalized, JSON_UNESCAPED_SLASHES);
}

function read_ledger_file(string $path): array
{
    $by_round = [];
    if (!is_readable($path)) {
        return $by_round;
    }
    $fh = fopen($path, 'r');
    fgetcsv($fh);
    while (($line = fgetcsv($fh)) !== false) {
        $rid = (int) $line[0];
        $by_round[$rid] = [
            'p1_action' => $line[2],
            'p2_action' => $line[3],
        ];
    }
    fclose($fh);
    return $by_round;
}

function step_d(array $merge, array $rules, array $poll): array
{
    $rulings = [];
    foreach ($poll['disputes'] ?? [] as $d) {
        $rulings[(int) $d['round_id']] = $d['ruling_side'];
    }
    $alpha_moves = [];
    $beta_moves = [];
    $alpha = read_ledger_file('/app/data/q7_a.csv');
    $beta = read_ledger_file('/app/data/q7_b.csv');
    foreach ($alpha as $rid => $row) {
        $alpha_moves[$rid] = [$row['p1_action'], $row['p2_action']];
    }
    foreach ($beta as $rid => $row) {
        $beta_moves[$rid] = [$row['p1_action'], $row['p2_action']];
    }
    $verdicts = [];
    foreach ($merge['merged_rounds'] as $row) {
        $rid = (int) $row['round_id'];
        $am = $alpha_moves[$rid] ?? ['', ''];
        $bm = $beta_moves[$rid] ?? ['', ''];
        $valid = ledger_moves_valid($rid, $am[0], $am[1], $rules)
            && ledger_moves_valid($rid, $bm[0], $bm[1], $rules);
        if (!$valid) {
            $verdicts[] = [
                'round_id' => $rid,
                'winner' => 'void',
                'resolution_source' => 'rule_void',
                'moves_valid' => false,
            ];
            continue;
        }
        if ($row['q7_a_winner'] === $row['q7_b_winner']) {
            $verdicts[] = [
                'round_id' => $rid,
                'winner' => $row['q7_a_winner'],
                'resolution_source' => 'cabinet_agree',
                'moves_valid' => true,
            ];
            continue;
        }
        $verdicts[] = [
            'round_id' => $rid,
            'winner' => $rulings[$rid] ?? 'void',
            'resolution_source' => 'referee',
            'moves_valid' => true,
        ];
    }
    usort($verdicts, fn($a, $b) => $a['round_id'] <=> $b['round_id']);
    return [
        'verdicts' => $verdicts,
        'batch_digest' => hash('sha256', sorted_verdicts_json($verdicts)),
    ];
}
