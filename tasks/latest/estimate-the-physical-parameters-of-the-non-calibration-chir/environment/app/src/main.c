#include <stdio.h>
#include <stdlib.h>

#include "catalog.h"
#include "obs.h"
#include "output.h"
#include "recover.h"

int main(int argc, char **argv) {
    const char *catalog_path = "/app/catalog.sqlite";
    const char *obs_dir = "/app/observations";
    const char *json_path = "/app/output/events.json";
    const char *sqlite_path = "/app/output/recovered.sqlite";

    if (argc == 5) {
        catalog_path = argv[1];
        obs_dir = argv[2];
        json_path = argv[3];
        sqlite_path = argv[4];
    } else if (argc != 1) {
        fprintf(stderr, "usage: %s [catalog.sqlite observations_dir events.json recovered.sqlite]\n", argv[0]);
        return 2;
    }

    Catalog catalog = {0};
    ObservationSet observations = {0};
    RecoveryResult result = {0};
    int rc = 1;

    if (load_catalog(catalog_path, &catalog) != 0) {
        fprintf(stderr, "failed to load catalog: %s\n", catalog_path);
        goto done;
    }
    if (load_observations(obs_dir, &observations) != 0) {
        fprintf(stderr, "failed to load observations: %s\n", obs_dir);
        goto done;
    }
    if (recover_events(&catalog, &observations, &result) != 0) {
        fprintf(stderr, "recovery failed\n");
        goto done;
    }
    if (write_events_json(json_path, &result) != 0) {
        fprintf(stderr, "failed to write %s\n", json_path);
        goto done;
    }
    if (write_events_sqlite(sqlite_path, &result) != 0) {
        fprintf(stderr, "failed to write %s\n", sqlite_path);
        goto done;
    }

    rc = 0;

done:
    free_recovery_result(&result);
    free_observations(&observations);
    free_catalog(&catalog);
    return rc;
}
