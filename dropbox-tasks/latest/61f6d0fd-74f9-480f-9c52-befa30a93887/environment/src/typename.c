#include "dyeworks/typename.h"

/* The dyeworks-type names understood by the reduced reader. A container type
 * (range, vat, dyeworks) carries children; a leaf type (skein, mordant,
 * swatch) does not. */
const char *type_name(uint64_t type) {
    switch (type) {
        case 0x01:
            return "range";
        case 0x02:
            return "vat";
        case 0x03:
            return "dyeworks";
        case 0x04:
            return "skein";
        case 0x05:
            return "mordant";
        case 0x06:
            return "swatch";
        default:
            return "unknown";
    }
}
