<?php
declare(strict_types=1);

function read_overlay_rows(string $path): array
{
    $rows = [];
    if (!is_readable($path)) {
        return $rows;
    }
    $fh = fopen($path, 'r');
    fgetcsv($fh);
    while (($line = fgetcsv($fh)) !== false) {
        if (($line[0] ?? '') === '') {
            continue;
        }
        $rows[] = [
            'round_id' => (int) $line[0],
            'winner_side' => $line[4] ?? '',
            'flags' => $line[5] ?? '',
        ];
    }
    fclose($fh);
    return $rows;
}

function seal_f(array $cfg, string $combo_path, string $overlay_csv): array
{
    $verdict_path = $cfg['verdict_snapshot'] ?? '/app/output/verdict_snapshot.json';
    $upstream = '';
    if (is_readable($verdict_path)) {
        $doc = json_decode(file_get_contents($verdict_path), true);
        $upstream = $doc['batch_digest'] ?? '';
    }
    $combo_total = 0;
    if (is_readable($combo_path)) {
        $combo = json_decode(file_get_contents($combo_path), true);
        $combo_total = (int) ($combo['combo_total'] ?? 0);
    }
    $overlay = read_overlay_rows($overlay_csv);
    $overlay_verdicts = [];
    foreach ($overlay as $row) {
        $overlay_verdicts[] = [
            'round_id' => $row['round_id'],
            'winner' => $row['winner_side'],
            'resolution_source' => 'overlay_lane',
        ];
    }
    usort($overlay_verdicts, fn($a, $b) => $a['round_id'] <=> $b['round_id']);
    $seal_input = json_encode([
        'combo_total' => $combo_total,
        'overlay_void_ids' => [],
        'upstream_digest' => $upstream,
    ]);
    return [
        'overlay_rows' => count($overlay),
        'overlay_void_ids' => [],
        'overlay_verdicts' => $overlay_verdicts,
        'combo_total' => $combo_total,
        'upstream_digest' => $upstream,
        'seal_digest' => md5($seal_input),
    ];
}
