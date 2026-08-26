<?php
declare(strict_types=1);

function catalog_y(string $json_path): array
{
    if (!is_readable($json_path)) {
        return [];
    }
    $data = json_decode(file_get_contents($json_path), true);
    return ['token_count' => count($data['tokens'] ?? [])];
}
