#pragma once
#include "types.h"
#include <cstdint>
#include <string>

int row_junction_peak(const Fragment& left, const Fragment& right, bool case_fold);
int row_junction_overlap(const Fragment& left, const Fragment& right, int min_overlap, bool case_fold);
