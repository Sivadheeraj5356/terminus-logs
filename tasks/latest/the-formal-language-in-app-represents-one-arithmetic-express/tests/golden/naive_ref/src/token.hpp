#pragma once

#include <string>

enum class TokKind {
  Number,
  Ident,
  Plus,
  Minus,
  Star,
  Slash,
  LParen,
  RParen,
  End
};

struct Token {
  TokKind kind;
  double number = 0.0;
  std::string text;
};
