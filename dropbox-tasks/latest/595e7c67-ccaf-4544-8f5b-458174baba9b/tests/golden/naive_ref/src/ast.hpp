#pragma once

#include <memory>
#include <string>

enum class NodeKind { Num, Var, Add, Sub, Mul, Div, Neg };

struct Node {
  NodeKind kind;
  double num = 0.0;
  std::string name;
  std::unique_ptr<Node> a;
  std::unique_ptr<Node> b;
};

using NodePtr = std::unique_ptr<Node>;

inline NodePtr makeNum(double v) {
  auto n = std::make_unique<Node>();
  n->kind = NodeKind::Num;
  n->num = v;
  return n;
}

inline NodePtr makeVar(const std::string& s) {
  auto n = std::make_unique<Node>();
  n->kind = NodeKind::Var;
  n->name = s;
  return n;
}

inline NodePtr makeBin(NodeKind k, NodePtr a, NodePtr b) {
  auto n = std::make_unique<Node>();
  n->kind = k;
  n->a = std::move(a);
  n->b = std::move(b);
  return n;
}

inline NodePtr makeNeg(NodePtr a) {
  auto n = std::make_unique<Node>();
  n->kind = NodeKind::Neg;
  n->a = std::move(a);
  return n;
}
