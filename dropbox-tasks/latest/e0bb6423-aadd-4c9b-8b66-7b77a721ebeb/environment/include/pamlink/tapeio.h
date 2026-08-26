#pragma once
#include "pamlink/types.h"
int tape_read(const char *path, tape_event *out, int max, int *count);
