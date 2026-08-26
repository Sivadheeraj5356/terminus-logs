<?php
declare(strict_types=1);

function phase_c(string $base_url, array $round_ids): array
{
    $ids = implode(',', $round_ids);
    $url = rtrim($base_url, '/') . '/rounds/disputed?ids=' . urlencode($ids);
    $raw = @file_get_contents($url);
    $payload = $raw ? json_decode($raw, true) : [];
    return [
        'dispute_count' => 0,
        'disputes' => $payload['items'] ?? [],
        'fw_q7_a' => '',
        'fw_q7_b' => '',
    ];
}
