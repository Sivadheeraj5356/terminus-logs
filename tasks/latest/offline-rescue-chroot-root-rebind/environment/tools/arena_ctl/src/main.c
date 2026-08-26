#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/stat.h>

#define ARENA_PATH "/app/output/.pack_arena"
#define ARENA_MAGIC 0x43534B50u
#define RESET_MARKER 0x44454553u

typedef struct {
    uint32_t magic;
    uint32_t generation;
    uint32_t dirty;
    uint32_t marker;
} arena_hdr;

static int write_hdr(const arena_hdr *hdr) {
    FILE *fp;
    mkdir("/app/output", 0755);
    fp = fopen(ARENA_PATH, "wb");
    if (!fp) {
        return 1;
    }
    if (fwrite(hdr, sizeof(*hdr), 1, fp) != 1) {
        fclose(fp);
        return 1;
    }
    fclose(fp);
    return 0;
}

static int apply_reset(const char *reset_path) {
    FILE *fp;
    uint8_t buf[64];
    size_t n;
    arena_hdr hdr;

    fp = fopen(reset_path, "rb");
    if (!fp) {
        fprintf(stderr, "missing reset file: %s\n", reset_path);
        return 1;
    }
    n = fread(buf, 1, sizeof(buf), fp);
    fclose(fp);
    if (n < 4) {
        fprintf(stderr, "reset file too short\n");
        return 1;
    }

    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = ARENA_MAGIC;
    hdr.generation = 0;
    hdr.dirty = 0;
    hdr.marker = RESET_MARKER;
    hdr.marker ^= (uint32_t)buf[0] | ((uint32_t)buf[1] << 8);
    return write_hdr(&hdr);
}

static int corrupt_arena(void) {
    arena_hdr hdr;
    memset(&hdr, 0, sizeof(hdr));
    hdr.magic = 0xDEADBEEFu;
    hdr.generation = 99;
    hdr.dirty = 1;
    hdr.marker = 0;
    return write_hdr(&hdr);
}

int main(int argc, char **argv) {
    if (argc >= 3 && strcmp(argv[1], "--apply-base") == 0) {
        return apply_reset(argv[2]);
    }
    if (argc >= 2 && strcmp(argv[1], "--corrupt") == 0) {
        return corrupt_arena();
    }
    fprintf(stderr, "usage: arena_ctl --apply-base <reset.bin> | --corrupt\n");
    return 1;
}
