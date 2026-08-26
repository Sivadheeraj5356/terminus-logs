#include <stdio.h>
#include <stdlib.h>
#include <sys/stat.h>

int main(int argc, char **argv) {
    const char *output_dir = argc > 2 ? argv[2] : "/app/task_file/output_data";
    char output_path[512];

    (void)argc;
    (void)argv;

    mkdir(output_dir, 0777);
    snprintf(output_path, sizeof(output_path), "%s/batches.json", output_dir);

    FILE *fh = fopen(output_path, "w");
    if (fh == NULL) {
        return 1;
    }

    fputs("{\"panels\":[],\"runs\":[]}\n", fh);
    fclose(fh);
    return 0;
}
