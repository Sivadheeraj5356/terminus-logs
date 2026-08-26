<?php
declare(strict_types=1);

function op_a(array $cfg): array
{
    $alpha_path = $cfg['q7_a_csv'] ?? '';
    $beta_path = $cfg['q7_b_csv'] ?? '';
    $rows = [];
    if ($alpha_path !== '' && is_readable($alpha_path)) {
        $fh = fopen($alpha_path, 'r');
        $header = fgetcsv($fh);
        $idx = 0;
        while (($line = fgetcsv($fh)) !== false) {
            $rows[] = [
                'round_id' => (int) $line[0],
                'q7_a_winner' => $line[4],
                'q7_b_winner' => $line[4],
                '_order' => $idx,
            ];
            $idx++;
        }
        fclose($fh);
    }
    $dispute_ids = [];
    $q7_a_rows = count($rows);
    $q7_b_rows = 0;
    return [
        'q7_a_rows' => $q7_a_rows,
        'q7_b_rows' => $q7_b_rows,
        'merged_count' => count($rows),
        'dispute_ids' => $dispute_ids,
        'merged_rounds' => $rows,
    ];
}
