#ifndef DYEWORKS_DYEWORKSDEF_H
#define DYEWORKS_DYEWORKSDEF_H

#include "dyeworks/types.h"

int dyeworksdef_parse(dyeworks_t *sp);

/* Locate the dyeworksdef declaration a node names by its type code, or NULL. */
const dyeworks_def_t *dyeworksdef_lookup(const dyeworks_t *sp, uint64_t code);
#endif
