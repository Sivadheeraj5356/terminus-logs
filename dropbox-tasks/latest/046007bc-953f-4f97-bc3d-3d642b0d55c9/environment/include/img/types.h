#ifndef IMG_TYPES_H
#define IMG_TYPES_H

#include <stddef.h>
#include <stdint.h>

/* Inode kinds. A file inode carries a run of resident data bytes; a directory
 * inode lists the inodes of its children by index. */
#define IMG_FILE 0
#define IMG_DIR 1

/* A parsed image inode. Resident data bytes and child indices are not copied out
 * of the file buffer; a directory inode records where its child-index list
 * begins so the resolver can re-read it, and a file inode records only its
 * resident byte count. */
typedef struct {
    uint8_t kind;
    uint32_t uid;         /* fixed-width owner id read at the inode start */
    int64_t mtime_delta;  /* signed inter-inode modification-time delta */
    uint32_t nbytes;      /* file: number of resident data bytes */
    uint32_t nchild;      /* directory: number of child inode indices */
    size_t child_off;     /* directory: file offset of the first child-index varint */
} img_inode_t;

/* The whole parsed disk image: the raw file, the located regions, the inode
 * array, and the derived counts reported in the summary. */
typedef struct {
    const uint8_t *buf;
    size_t n;

    uint8_t version;
    uint8_t region_count;

    const uint8_t *names;
    size_t names_size;
    const uint8_t *volumes;
    size_t volumes_size;
    const uint8_t *inodes;
    size_t inodes_size;
    const uint8_t *links;
    size_t links_size;
    const uint8_t *xattrs;
    size_t xattrs_size;

    img_inode_t *inode;
    size_t inode_count;
    size_t file_count;
    size_t dir_count;

    size_t volume_count;
    size_t link_count;
    size_t xattr_count;

    uint64_t vol_checksum;   /* forces the label scan a volume descriptor performs */
    uint64_t link_checksum;  /* forces the inode lookups a hardlink edge performs */
    uint64_t xattr_checksum; /* forces the value scan an xattr performs */

    long data_bytes;
} img_image_t;

#endif
