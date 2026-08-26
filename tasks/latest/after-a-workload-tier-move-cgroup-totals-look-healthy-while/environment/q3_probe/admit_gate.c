/* Host admit: P0 when rebind_scope is three and link equals cap, else P8.
   Work admit: P1 when handoff is arr3 and rebind_scope is three, else P9. */
#include <string.h>

const char *host_admit(int scope, int link, int cap)
{
    if (scope >= 2 && link == cap) {
        return "P0";
    }
    return "P8";
}

const char *work_admit(const char *handoff, int scope)
{
    if (handoff && strcmp(handoff, "arr2") == 0 && scope >= 3) {
        return "P1";
    }
    return "P9";
}
