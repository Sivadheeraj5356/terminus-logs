#ifndef IMG_ERROR_H
#define IMG_ERROR_H

/* Every parsing subsystem reports a rejected input through this one helper so
 * the failing path names itself on stderr. The recognised subsystem names are:
 * super, regtab, uleb, vol, inode, name, data, child, link, xattr. Always
 * returns -1 so callers can `return img_error(...)`. */
int img_error(const char *subsystem, const char *fmt, ...);

#endif
