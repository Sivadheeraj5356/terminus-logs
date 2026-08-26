#include "foldpath/config.h"

/*
 * Deliberate task scaffold. Strict raw-byte-aware configuration loading,
 * decimal grammar, schema validation, and typed model/control construction
 * are part of the deliverable.
 */

const char *fp_model_kind_name(fp_model_kind kind)
{
    switch (kind) {
    case FP_MODEL_CUBIC:
        return "cubic";
    case FP_MODEL_COUPLED:
        return "coupled";
    case FP_MODEL_BRATU:
        return "bratu";
    default:
        return NULL;
    }
}

fp_result fp_model_load(const char *path, fp_model *model, uint64_t *fingerprint)
{
    (void)path;
    (void)model;
    (void)fingerprint;
    return FP_INVALID;
}

fp_result fp_control_load(const char *path, fp_control *control, uint64_t *fingerprint)
{
    (void)path;
    (void)control;
    (void)fingerprint;
    return FP_INVALID;
}
