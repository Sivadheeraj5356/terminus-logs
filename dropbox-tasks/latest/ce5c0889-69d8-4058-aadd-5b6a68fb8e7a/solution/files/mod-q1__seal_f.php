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

function sorted_seal_json(int $combo_total, array $void_ids, string $upstream): string
{
    $payload = [
        'combo_total' => $combo_total,
        'overlay_void_ids' => $void_ids,
        'upstream_digest' => $upstream,
    ];
    ksort($payload);
    return json_encode($payload, JSON_UNESCAPED_SLASHES);
}

function seal_f(array $cfg, string $combo_path, string $overlay_csv): array
{
    $verdict_path = '/app/output/verdict_snapshots.json';
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
    $void_ids = [];
    $overlay_verdicts = [];
    foreach ($overlay as $row) {
        $rid = $row['round_id'];
        if (($row['flags'] ?? '') === 'forfeit') {
            $void_ids[] = $rid;
            $overlay_verdicts[] = [
                'round_id' => $rid,
                'winner' => 'void',
                'resolution_source' => 'forfeit',
            ];
            continue;
        }
        $overlay_verdicts[] = [
            'round_id' => $rid,
            'winner' => $row['winner_side'],
            'resolution_source' => 'overlay_lane',
        ];
    }
    sort($void_ids, SORT_NUMERIC);
    usort($overlay_verdicts, fn($a, $b) => $a['round_id'] <=> $b['round_id']);
    $seal_input = sorted_seal_json($combo_total, $void_ids, $upstream);
    return [
        'overlay_rows' => count($overlay),
        'overlay_void_ids' => $void_ids,
        'overlay_verdicts' => $overlay_verdicts,
        'combo_total' => $combo_total,
        'upstream_digest' => $upstream,
        'seal_digest' => hash('sha256', $seal_input),
    ];
}
