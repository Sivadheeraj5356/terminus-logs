<?php

declare(strict_types=1);

namespace IrisProv\Support;

final class JsonWriter
{
    public static function writePretty(string $path, array $doc): void
    {
        $encoded = json_encode($doc, JSON_PRETTY_PRINT | JSON_UNESCAPED_SLASHES);
        if ($encoded === false) {
            throw new \RuntimeException('json encode failed');
        }
        $lines = explode("\n", $encoded);
        $normalized = [];
        foreach ($lines as $line) {
            if (preg_match('/^(\s+)(.*)$/', $line, $matches)) {
                $depth = (int) (strlen($matches[1]) / 4);
                $normalized[] = str_repeat('  ', $depth) . $matches[2];
            } else {
                $normalized[] = $line;
            }
        }
        file_put_contents($path, implode("\n", $normalized) . "\n");
    }
}
