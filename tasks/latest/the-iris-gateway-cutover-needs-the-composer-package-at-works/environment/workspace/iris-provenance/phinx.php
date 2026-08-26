<?php

return [
    'paths' => [
        'migrations' => '%%PHINX_CONFIG_DIR%%/db/migrations',
    ],
    'environments' => [
        'default_migration_table' => 'phinxlog',
        'default_environment' => 'workspace',
        'workspace' => [
            'adapter' => 'sqlite',
            'name' => '/workspace/state/module-provenance',
        ],
    ],
    'version_order' => 'creation',
];
