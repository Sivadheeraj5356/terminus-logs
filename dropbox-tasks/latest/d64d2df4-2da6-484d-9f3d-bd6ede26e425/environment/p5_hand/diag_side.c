#include <stdio.h>

void diag_side_replay(const char *epoch_token)
{
    printf("diag replay token=%s\n", epoch_token ? epoch_token : "none");
}
