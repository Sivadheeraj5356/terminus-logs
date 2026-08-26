#include "printer.hpp"

#include <charconv>
#include <cmath>

static std::string numToStr(double v) {
  if (std::isnan(v)) {
    return "nan";
  }
  if (std::isinf(v)) {
    return v < 0 ? "-inf" : "inf";
  }
  if (v == 0.0) {
    return std::signbit(v) ? "-0.0" : "0.0";
  }
  char buf[64];
  auto res = std::to_chars(buf, buf + sizeof(buf), v);
  std::string s(buf, res.ptr);
  bool hasDotOrExp = false;
  for (char c : s) {
    if (c == '.' || c == 'e' || c == 'E') {
      hasDotOrExp = true;
      break;
    }
  }
  if (!hasDotOrExp) {
    s += ".0";
  }
  return s;
}

static const char* opStr(NodeKind k) {
  switch (k) {
    case NodeKind::Add:
      return "+";
    case NodeKind::Sub:
      return "-";
    case NodeKind::Mul:
      return "*";
    case NodeKind::Div:
      return "/";
    default:
      return "?";
  }
}

std::string printNode(const Node* n) {
  switch (n->kind) {
    case NodeKind::Num:
      return numToStr(n->num);
    case NodeKind::Var:
      return n->name;
    case NodeKind::Neg:
      return "-" + printNode(n->a.get());
    default:
      return "(" + printNode(n->a.get()) + " " + opStr(n->kind) + " " +
             printNode(n->b.get()) + ")";
  }
}
