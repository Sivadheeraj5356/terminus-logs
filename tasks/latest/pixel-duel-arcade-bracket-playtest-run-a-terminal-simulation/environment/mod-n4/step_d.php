<?php
declare(strict_types=1);

function step_d(array $merge, array $rules, array $poll): array
{
    $verdicts = [];
    foreach ($merge['merged_rounds'] as $row) {
        $rid = (int) $row['round_id'];
        $verdicts[] = [
            'round_id' => $rid,
            'winner' => $row['q7_a_winner'] ?? 'side_a',
            'resolution_source' => 'cabinet_agree',
            'moves_valid' => true,
        ];
    }
    usort($verdicts, fn($a, $b) => $a['round_id'] <=> $b['round_id']);
    $canonical = json_encode($verdicts, JSON_UNESCAPED_SLASHES);
    return [
        'verdicts' => $verdicts,
        'batch_digest' => hash('sha256', $canonical),
    ];
}
