<?php
declare(strict_types=1);

function scan_x(string $csv_path): int
{
    if (!is_readable($csv_path)) {
        return 0;
    }
    $fh = fopen($csv_path, 'r');
    $header = fgetcsv($fh);
    fclose($fh);
    return count($header ?: []);
}
