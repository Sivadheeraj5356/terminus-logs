#include "foldpath/output.h"

/*
 * Deliberate task scaffold. Names are usable by candidate code, but strict
 * finite NDJSON generation and atomic publication are part of the deliverable.
 */

const char *fp_status_name(fp_status status)
{
    switch (status) {
    case FP_STATUS_PARTIAL:
        return "partial";
    case FP_STATUS_COMPLETE:
        return "complete";
    case FP_STATUS_STALLED:
        return "stalled";
    default:
        return NULL;
    }
}

const char *fp_fold_name(fp_fold fold)
{
    switch (fold) {
    case FP_FOLD_NONE:
        return "none";
    case FP_FOLD_MAX_LAMBDA:
        return "max_lambda";
    case FP_FOLD_MIN_LAMBDA:
        return "min_lambda";
    default:
        return NULL;
    }
}

fp_result fp_output_write_atomic(const char *path, const fp_state *state)
{
    (void)path;
    (void)state;
    return FP_INVALID;
}
