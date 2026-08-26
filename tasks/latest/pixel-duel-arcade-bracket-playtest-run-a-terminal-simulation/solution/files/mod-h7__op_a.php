<?php
declare(strict_types=1);

function read_ledger(string $path): array
{
    $by_round = [];
    $fh = fopen($path, 'r');
    fgetcsv($fh);
    while (($line = fgetcsv($fh)) !== false) {
        if (($line[0] ?? '') === '') {
            continue;
        }
        $rid = (int) $line[0];
        $by_round[$rid] = [
            'round_id' => $rid,
            'cabinet_tag' => $line[1],
            'p1_action' => $line[2],
            'p2_action' => $line[3],
            'winner_side' => $line[4],
        ];
    }
    fclose($fh);
    return $by_round;
}

function op_a(array $cfg): array
{
    $alpha = read_ledger($cfg['q7_a_csv'] ?? '');
    $beta = read_ledger($cfg['q7_b_csv'] ?? '');
    $ids = array_unique(array_merge(array_keys($alpha), array_keys($beta)));
    sort($ids, SORT_NUMERIC);
    $merged = [];
    $dispute_ids = [];
    foreach ($ids as $rid) {
        $aw = $alpha[$rid]['winner_side'] ?? '';
        $bw = $beta[$rid]['winner_side'] ?? '';
        if ($aw !== $bw) {
            $dispute_ids[] = $rid;
        }
        $merged[] = [
            'round_id' => $rid,
            'q7_a_winner' => $aw,
            'q7_b_winner' => $bw,
        ];
    }
    return [
        'q7_a_rows' => count($alpha),
        'q7_b_rows' => count($beta),
        'merged_count' => count($merged),
        'dispute_ids' => $dispute_ids,
        'merged_rounds' => $merged,
    ];
}
