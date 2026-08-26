<?php
declare(strict_types=1);

function score_e(string $db_path, array $verdicts, string $lane_csv): array
{
    $valid = [];
    foreach ($verdicts as $row) {
        if (!empty($row['moves_valid'])) {
            $valid[(int) $row['round_id']] = true;
        }
    }
    $action_count = 0;
    if (is_readable($lane_csv)) {
        $fh = fopen($lane_csv, 'r');
        fgetcsv($fh);
        while (($line = fgetcsv($fh)) !== false) {
            if (($line[0] ?? '') === '') {
                continue;
            }
            $action_count++;
        }
        fclose($fh);
    }
    return [
        'combo_hits' => [],
        'combo_total' => 0,
        'rounds_scored' => min($action_count, count($valid)),
    ];
}
