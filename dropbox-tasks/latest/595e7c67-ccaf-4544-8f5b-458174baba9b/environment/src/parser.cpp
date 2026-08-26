#include "parser.hpp"

#include <stdexcept>

namespace {

struct Parser {
  const std::vector<Token>& t;
  size_t i = 0;

  explicit Parser(const std::vector<Token>& toks) : t(toks) {}

  const Token& cur() const { return t[i]; }

  void adv() { i++; }

  NodePtr parseExpr() {
    NodePtr left = parseTerm();
    while (cur().kind == TokKind::Plus || cur().kind == TokKind::Minus) {
      TokKind op = cur().kind;
      adv();
      NodePtr right = parseTerm();
      NodeKind k = op == TokKind::Plus ? NodeKind::Add : NodeKind::Sub;
      left = makeBin(k, std::move(left), std::move(right));
    }
    return left;
  }

  NodePtr parseTerm() {
    NodePtr left = parseFactor();
    while (cur().kind == TokKind::Star || cur().kind == TokKind::Slash) {
      TokKind op = cur().kind;
      adv();
      NodePtr right = parseFactor();
      NodeKind k = op == TokKind::Star ? NodeKind::Mul : NodeKind::Div;
      left = makeBin(k, std::move(left), std::move(right));
    }
    return left;
  }

  NodePtr parseFactor() {
    if (cur().kind == TokKind::Minus) {
      adv();
      NodePtr inner = parseFactor();
      if (inner->kind == NodeKind::Num) {
        return makeNum(-inner->num);
      }
      return makeNeg(std::move(inner));
    }
    return parseAtom();
  }

  NodePtr parseAtom() {
    if (cur().kind == TokKind::Number) {
      double v = cur().number;
      adv();
      return makeNum(v);
    }
    if (cur().kind == TokKind::Ident) {
      std::string s = cur().text;
      adv();
      return makeVar(s);
    }
    if (cur().kind == TokKind::LParen) {
      adv();
      NodePtr e = parseExpr();
      if (cur().kind != TokKind::RParen) {
        throw std::runtime_error("expected )");
      }
      adv();
      return e;
    }
    throw std::runtime_error("parse error");
  }
};

}

NodePtr parse(const std::vector<Token>& toks) {
  Parser p(toks);
  NodePtr e = p.parseExpr();
  if (p.cur().kind != TokKind::End) {
    throw std::runtime_error("trailing tokens");
  }
  return e;
}
