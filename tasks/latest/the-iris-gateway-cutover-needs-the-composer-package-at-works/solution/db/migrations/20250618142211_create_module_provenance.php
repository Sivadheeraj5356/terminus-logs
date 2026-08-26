<?php

declare(strict_types=1);

use Phinx\Migration\AbstractMigration;

final class CreateModuleProvenance extends AbstractMigration
{
    public function change(): void
    {
        $this->table('module_units', ['id' => false, 'primary_key' => ['module_path', 'version']])
            ->addColumn('module_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('version', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('checksum_sha256', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('go_version', 'string', ['limit' => 32, 'null' => false])
            ->addColumn('is_root', 'integer', ['null' => false])
            ->create();

        $this->table(
            'module_edges',
            ['id' => false, 'primary_key' => ['parent_path', 'parent_version', 'child_path', 'child_version', 'edge_kind']]
        )
            ->addColumn('parent_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('parent_version', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('child_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('child_version', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('edge_kind', 'string', ['limit' => 16, 'null' => false])
            ->create();

        $this->table(
            'replace_rules',
            ['id' => false, 'primary_key' => ['scope_path', 'scope_version', 'old_path', 'old_version']]
        )
            ->addColumn('scope_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('scope_version', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('old_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('old_version', 'string', ['limit' => 64, 'null' => false])
            ->addColumn('new_path', 'string', ['limit' => 255, 'null' => false])
            ->addColumn('new_version', 'string', ['limit' => 64, 'null' => false])
            ->create();
    }
}
