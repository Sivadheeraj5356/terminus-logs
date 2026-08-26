#pragma once

#include <vector>

#include "ast.hpp"
#include "token.hpp"

NodePtr parse(const std::vector<Token>& toks);
