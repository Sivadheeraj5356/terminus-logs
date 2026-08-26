#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "img/inode.h"
#include "img/error.h"
#include "img/json.h"
#include "img/link.h"
#include "img/reader.h"
#include "img/regtab.h"
#include "img/super.h"
#include "img/types.h"
#include "img/version.h"
#include "img/vol.h"
#include "img/xattr.h"

int main(int argc, char **argv) {
    if (argc == 2 && strcmp(argv[1], "--version") == 0) {
        printf("imgscan %s\n", img_tool_version());
        return 0;
    }
    if (argc != 2) {
        fprintf(stderr, "usage: imgscan <file>\n");
        return 2;
    }

    img_image_t c;
    memset(&c, 0, sizeof(c));

    uint8_t *buf = NULL;
    size_t n = 0;
    if (img_load_file(argv[1], &buf, &n) < 0) {
        return 1;
    }
    c.buf = buf;
    c.n = n;

    int rc = 0;
    if (img_super_parse(&c) < 0) {
        rc = 1;
    } else if (img_regtab_parse(&c) < 0) {
        rc = 1;
    } else if (img_vol_parse(&c) < 0) {
        rc = 1;
    } else if (img_inode_parse(&c) < 0) {
        rc = 1;
    } else if (img_link_parse(&c) < 0) {
        rc = 1;
    } else if (img_xattr_parse(&c) < 0) {
        rc = 1;
    } else if (img_inode_resolve(&c) < 0) {
        rc = 1;
    }

    if (rc == 0) {
        img_write_summary(stdout, &c);
    }

    free(c.inode);
    free(buf);
    return rc;
}
