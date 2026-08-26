<?php
declare(strict_types=1);

function phase_c(string $base_url, array $round_ids): array
{
    $ids = implode(',', $round_ids);
    $url = rtrim($base_url, '/') . '/v1/disputes?round_ids=' . urlencode($ids);
    $raw = file_get_contents($url);
    if ($raw === false) {
        return [
            'dispute_count' => 0,
            'disputes' => [],
            'fw_q7_a' => '',
            'fw_q7_b' => '',
        ];
    }
    $payload = json_decode($raw, true);
    $disputes = $payload['disputes'] ?? [];
    $meta = $payload['cabinet_meta'] ?? [];
    return [
        'dispute_count' => count($disputes),
        'disputes' => $disputes,
        'fw_q7_a' => $meta['red-cab']['firmware'] ?? '',
        'fw_q7_b' => $meta['blue-cab']['firmware'] ?? '',
    ];
}
