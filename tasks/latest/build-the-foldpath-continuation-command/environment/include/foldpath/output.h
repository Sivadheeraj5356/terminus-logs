#ifndef FOLDPATH_OUTPUT_H
#define FOLDPATH_OUTPUT_H

#include "foldpath/types.h"

const char *fp_status_name(fp_status status);
const char *fp_fold_name(fp_fold fold);
fp_result fp_output_write_atomic(const char *path, const fp_state *state);

#endif
