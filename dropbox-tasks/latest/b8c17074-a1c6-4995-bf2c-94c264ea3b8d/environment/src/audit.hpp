#pragma once

#include <string>

int audit_fits(const std::string& path);
int render_from_fits(const std::string& fits_path, const std::string& svg_path);
int sample_fits(const std::string& fits_path, const std::string& sx, const std::string& sy);
