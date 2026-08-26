#include "img/json.h"

/* One-line JSON object carrying the summary fields. Key order is not
 * significant: the line is parsed back into an object by whatever consumes it. */
void img_write_summary(FILE *out, const img_image_t *c) {
    fprintf(out,
            "{\"format_version\":%u,\"volumes_defined\":%zu,"
            "\"inodes_defined\":%zu,\"file_inodes\":%zu,"
            "\"dir_inodes\":%zu,\"hardlinks_parsed\":%zu,"
            "\"xattrs_parsed\":%zu,\"data_bytes\":%ld}\n",
            (unsigned)c->version, c->volume_count, c->inode_count,
            c->file_count, c->dir_count, c->link_count, c->xattr_count,
            c->data_bytes);
}
