#include "folder.hpp"

#include <cmath>

static bool sameTree(const Node* a, const Node* b) {
  if (a->kind != b->kind) {
    return false;
  }
  switch (a->kind) {
    case NodeKind::Num:
      return a->num == b->num || (std::isnan(a->num) && std::isnan(b->num));
    case NodeKind::Var:
      return a->name == b->name;
    case NodeKind::Neg:
      return sameTree(a->a.get(), b->a.get());
    default:
      return sameTree(a->a.get(), b->a.get()) && sameTree(a->b.get(), b->b.get());
  }
}

static bool isConst(const Node* n, double v) {
  return n->kind == NodeKind::Num && n->num == v;
}

static double apply(NodeKind k, double x, double y) {
  switch (k) {
    case NodeKind::Add:
      return x + y;
    case NodeKind::Sub:
      return x - y;
    case NodeKind::Mul:
      return x * y;
    case NodeKind::Div:
      return x / y;
    default:
      return 0.0;
  }
}

NodePtr fold(NodePtr node) {
  if (node->kind == NodeKind::Num || node->kind == NodeKind::Var) {
    return node;
  }
  if (node->kind == NodeKind::Neg) {
    node->a = fold(std::move(node->a));
    if (node->a->kind == NodeKind::Num) {
      return makeNum(-node->a->num);
    }
    if (node->a->kind == NodeKind::Neg) {
      return std::move(node->a->a);
    }
    return node;
  }
  node->a = fold(std::move(node->a));
  node->b = fold(std::move(node->b));
  Node* a = node->a.get();
  Node* b = node->b.get();
  if (a->kind == NodeKind::Num && b->kind == NodeKind::Num) {
    return makeNum(apply(node->kind, a->num, b->num));
  }
  switch (node->kind) {
    case NodeKind::Add:
      if (isConst(a, 0.0)) {
        return std::move(node->b);
      }
      if (isConst(b, 0.0)) {
        return std::move(node->a);
      }
      if (a->kind == NodeKind::Add && a->b->kind == NodeKind::Num &&
          b->kind == NodeKind::Num) {
        double c = a->b->num + b->num;
        return makeBin(NodeKind::Add, std::move(node->a->a), makeNum(c));
      }
      break;
    case NodeKind::Sub:
      if (isConst(b, 0.0)) {
        return std::move(node->a);
      }
      if (isConst(a, 0.0)) {
        return makeNeg(std::move(node->b));
      }
      if (sameTree(a, b)) {
        return makeNum(0.0);
      }
      break;
    case NodeKind::Mul:
      if (isConst(a, 1.0)) {
        return std::move(node->b);
      }
      if (isConst(b, 1.0)) {
        return std::move(node->a);
      }
      if (isConst(a, 0.0)) {
        return makeNum(0.0);
      }
      if (isConst(b, 0.0)) {
        return makeNum(0.0);
      }
      if (a->kind == NodeKind::Mul && a->b->kind == NodeKind::Num &&
          b->kind == NodeKind::Num) {
        double c = a->b->num * b->num;
        return makeBin(NodeKind::Mul, std::move(node->a->a), makeNum(c));
      }
      break;
    case NodeKind::Div:
      if (isConst(b, 1.0)) {
        return std::move(node->a);
      }
      if (sameTree(a, b)) {
        return makeNum(1.0);
      }
      break;
    default:
      break;
  }
  return node;
}
