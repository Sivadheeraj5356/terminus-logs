#include "folder.hpp"

#include <cmath>

static bool isZero(const Node* n) {
  return n->kind == NodeKind::Num && n->num == 0.0;
}

static bool isOne(const Node* n) {
  return n->kind == NodeKind::Num && n->num == 1.0;
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
      if (isZero(a)) {
        return std::move(node->b);
      }
      if (isZero(b)) {
        return std::move(node->a);
      }
      break;
    case NodeKind::Sub:
      if (isZero(b)) {
        return std::move(node->a);
      }
      break;
    case NodeKind::Mul:
      if (isOne(a)) {
        return std::move(node->b);
      }
      if (isOne(b)) {
        return std::move(node->a);
      }
      break;
    case NodeKind::Div:
      if (isOne(b)) {
        return std::move(node->a);
      }
      break;
    default:
      break;
  }
  return node;
}
