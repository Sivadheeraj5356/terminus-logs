#include "stage_mesh.h"

#include "ac_sha.h"

#include <cstdio>
#include <cstring>
#include <sys/stat.h>

static int ensure_dir(const char *path) {
    struct stat st;
    if (stat(path, &st) == 0) {
        return S_ISDIR(st.st_mode) ? 0 : -1;
    }
    return mkdir(path, 0755);
}

int stage_mesh_speed_digest(const ac_speed_map *speed, char *out_hex, int out_len) {
    char payload[65536];
    int off = 0;
    for (int y = 0; y < speed->ny; ++y) {
        for (int x = 0; x < speed->nx; ++x) {
            const int iv = static_cast<int>(speed->c[y * speed->nx + x]);
            off += snprintf(payload + off, sizeof payload - off, "%d,", iv);
            if (off >= static_cast<int>(sizeof payload) - 32) {
                break;
            }
        }
    }
    ac_sha256_hex(payload, out_hex, out_len);
    return 0;
}

int stage_mesh_write(const char *profile, const ac_ct_volume *vol, const ac_speed_map *speed) {
    if (ensure_dir("/app/state") != 0) {
        return -1;
    }
    char prof_dir[512];
    snprintf(prof_dir, sizeof prof_dir, "/app/state/%s", profile);
    if (ensure_dir(prof_dir) != 0) {
        return -1;
    }
    int air = 0;
    int wood = 0;
    for (int i = 0; i < vol->nx * vol->ny; ++i) {
        if (vol->voxels[i] == 0) {
            ++wood;
        } else {
            ++air;
        }
    }
    char digest[65];
    stage_mesh_speed_digest(speed, digest, 65);
    char path[576];
    snprintf(path, sizeof path, "%s/cavity_mesh.json", prof_dir);
    FILE *fp = fopen(path, "w");
    if (!fp) {
        return -1;
    }
    fprintf(fp, "{\n");
    fprintf(fp, "  \"profile\": \"%s\",\n", profile);
    fprintf(fp, "  \"nx\": %d,\n", vol->nx);
    fprintf(fp, "  \"ny\": %d,\n", vol->ny);
    fprintf(fp, "  \"air_cells\": %d,\n", air);
    fprintf(fp, "  \"wood_cells\": %d,\n", wood);
    fprintf(fp, "  \"speed_digest\": \"%s\",\n", digest);
    fprintf(fp, "  \"protocol_epoch\": 1\n");
    fprintf(fp, "}\n");
    fclose(fp);
    return 0;
}

int stage_mesh_read_digest(const char *profile, char *out_hex, int out_len) {
    char path[576];
    snprintf(path, sizeof path, "/app/state/%s/cavity_mesh.json", profile);
    FILE *fp = fopen(path, "r");
    if (!fp) {
        return -1;
    }
    char line[1024];
    out_hex[0] = '\0';
    while (fgets(line, sizeof line, fp)) {
        const char *key = strstr(line, "\"speed_digest\"");
        if (!key) {
            continue;
        }
        const char *q1 = strchr(key, ':');
        if (!q1) {
            continue;
        }
        q1 = strchr(q1, '"');
        if (!q1) {
            continue;
        }
        ++q1;
        const char *q2 = strchr(q1, '"');
        if (!q2) {
            continue;
        }
        const int n = static_cast<int>(q2 - q1);
        if (n >= out_len) {
            fclose(fp);
            return -1;
        }
        memcpy(out_hex, q1, n);
        out_hex[n] = '\0';
        fclose(fp);
        return 0;
    }
    fclose(fp);
    return -1;
}
