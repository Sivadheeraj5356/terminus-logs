#ifndef GENABI_RENDER_HPP
#define GENABI_RENDER_HPP

#include <string>

#include "common.hpp"

bool render_header(const std::string &path, const LaneModel &model);
bool render_layout(const std::string &path, const LaneModel &model);

#endif
