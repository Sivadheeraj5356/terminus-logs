#include <string.h>

int op_u4(const char *tier_tag, int link_cap, const char *ns_token, int *link_out, int *epoch_out)
{
    (void)tier_tag;
    *link_out = link_cap > 0 ? link_cap : 1;
    *epoch_out = 1;
    if (ns_token && strstr(ns_token, "ns_gen_b")) {
        *epoch_out = 1;
    } else if (ns_token && strstr(ns_token, "ns_gen_a")) {
        *epoch_out = 1;
    }
    return 0;
}
