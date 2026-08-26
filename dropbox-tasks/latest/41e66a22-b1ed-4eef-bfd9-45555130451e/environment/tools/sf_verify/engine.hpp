#pragma once
#include "types.hpp"
#include <string>
#include <vector>

int run_matrix_engine(const std::string &env_root,
                      const std::string &matrix,
                      const std::vector<std::string> &profiles,
                      const std::string &witness_out,
                      run_matrix *out_mx);
