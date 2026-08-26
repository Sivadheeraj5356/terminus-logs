#include <stdio.h>
#include <string.h>

int gate_p5(const char *epoch_id, const char *site_id, int inherit_arr, int pin_scope,
            char *handoff_out, size_t handoff_cap)
{
    (void)epoch_id;
    if (inherit_arr == 0) {
        snprintf(handoff_out, handoff_cap, "arr1");
        return 0;
    }
    if (site_id && strcmp(site_id, "site_p7") == 0) {
        snprintf(handoff_out, handoff_cap, "arr2");
        return 0;
    }
    snprintf(handoff_out, handoff_cap, "arr2");
    return 0;
}
