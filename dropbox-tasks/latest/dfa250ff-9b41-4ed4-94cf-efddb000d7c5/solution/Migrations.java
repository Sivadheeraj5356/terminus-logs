package com.aurora.registry;

import java.util.ArrayList;
import java.util.List;

/**
 * The registered migration set, in application order.
 *
 * <p>Every migration the runner knows about is listed here. A new migration is added by appending
 * it to this list with the next version number; the runner applies whatever is registered and has
 * not yet been recorded in the ledger.
 */
public final class Migrations {

    private Migrations() {
    }

    public static List<Migration> all() {
        List<Migration> migrations = new ArrayList<>();
        migrations.add(new SqlMigration(1, "V1__registry_core.sql"));
        migrations.add(new SqlMigration(2, "V2__seed_model_runs.sql"));
        migrations.add(new SqlMigration(3, "V3__seed_feature_catalog.sql"));
        migrations.add(new SqlMigration(4, "V4__cohort_register.sql"));
        migrations.add(new SqlMigration(5, "V5__seed_cohort_register.sql"));
        migrations.add(new SqlMigration(6, "V6__promotion_decision_vocabulary.sql"));
        migrations.add(new V7LoadFeatureAudit());
        return migrations;
    }
}
