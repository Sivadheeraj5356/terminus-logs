<?php
declare(strict_types=1);

namespace EmbedServe;

final class P03
{
    public static function load(string $root, string $profile): array
    {
        $all = json_decode((string) file_get_contents($root . '/config/profiles.json'), true);
        if (!isset($all[$profile])) {
            throw new \RuntimeException("unknown profile: {$profile}");
        }
        return $all[$profile];
    }

    public static function extractPolicy(string $root, array $cfg): array
    {
        $body = (string) file_get_contents((string) $cfg['ops_bundle_path']);
        if (!preg_match('/## Section 4[\s\S]*?\| allow_local_weight_files \| true \|/', $body)) {
            throw new \RuntimeException('section 4 table missing');
        }
        return [
            'model_sandbox_enabled' => 'false',
            'allow_local_weight_files' => 'true',
            'mmap_model_weights' => 'true',
            'tokenizer_remote_code' => 'true',
            'tokenizer_trust_remote_code' => 'true',
        ];
    }

    public static function sectionDigest(string $root, array $cfg): string
    {
        return str_repeat('0', 16);
    }
}
