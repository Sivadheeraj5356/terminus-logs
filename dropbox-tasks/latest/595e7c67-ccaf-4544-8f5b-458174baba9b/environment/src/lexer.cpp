#include "lexer.hpp"

#include <cstdlib>
#include <limits>
#include <stdexcept>

static bool isIdentStart(char c) {
  return (c >= 'a' && c <= 'z') || c == '_';
}

static bool isIdentPart(char c) {
  return isIdentStart(c) || (c >= '0' && c <= '9');
}

static bool isDigit(char c) {
  return c >= '0' && c <= '9';
}

std::vector<Token> lex(const std::string& src) {
  std::vector<Token> out;
  size_t i = 0;
  size_t n = src.size();
  while (i < n) {
    char c = src[i];
    if (c == ' ' || c == '\t' || c == '\n' || c == '\r') {
      i++;
      continue;
    }
    if (c == '+') {
      out.push_back({TokKind::Plus});
      i++;
      continue;
    }
    if (c == '-') {
      out.push_back({TokKind::Minus});
      i++;
      continue;
    }
    if (c == '*') {
      out.push_back({TokKind::Star});
      i++;
      continue;
    }
    if (c == '/') {
      out.push_back({TokKind::Slash});
      i++;
      continue;
    }
    if (c == '(') {
      out.push_back({TokKind::LParen});
      i++;
      continue;
    }
    if (c == ')') {
      out.push_back({TokKind::RParen});
      i++;
      continue;
    }
    if (isIdentStart(c)) {
      size_t j = i;
      while (j < n && isIdentPart(src[j])) {
        j++;
      }
      std::string word = src.substr(i, j - i);
      i = j;
      if (word == "inf") {
        Token t;
        t.kind = TokKind::Number;
        t.number = std::numeric_limits<double>::infinity();
        out.push_back(t);
      } else if (word == "nan") {
        Token t;
        t.kind = TokKind::Number;
        t.number = std::numeric_limits<double>::quiet_NaN();
        out.push_back(t);
      } else {
        Token t;
        t.kind = TokKind::Ident;
        t.text = word;
        out.push_back(t);
      }
      continue;
    }
    if (isDigit(c) || c == '.') {
      size_t j = i;
      while (j < n && (isDigit(src[j]) || src[j] == '.')) {
        j++;
      }
      if (j < n && (src[j] == 'e' || src[j] == 'E')) {
        j++;
        if (j < n && (src[j] == '+' || src[j] == '-')) {
          j++;
        }
        while (j < n && isDigit(src[j])) {
          j++;
        }
      }
      std::string numstr = src.substr(i, j - i);
      i = j;
      Token t;
      t.kind = TokKind::Number;
      t.number = std::strtod(numstr.c_str(), nullptr);
      out.push_back(t);
      continue;
    }
    throw std::runtime_error("lex error");
  }
  out.push_back({TokKind::End});
  return out;
}
