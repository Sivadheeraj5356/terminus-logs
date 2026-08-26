import math
import struct


class Node:
    __slots__ = ("kind", "num", "name", "a", "b")

    def __init__(self, kind, num=0.0, name="", a=None, b=None):
        self.kind = kind
        self.num = num
        self.name = name
        self.a = a
        self.b = b


def lex(src):
    toks = []
    i = 0
    n = len(src)
    while i < n:
        c = src[i]
        if c in " \t\n\r":
            i += 1
            continue
        if c in "+-*/()":
            toks.append((c, None))
            i += 1
            continue
        if c.isalpha() or c == "_":
            j = i
            while j < n and (src[j].isalnum() or src[j] == "_"):
                j += 1
            word = src[i:j]
            i = j
            if word == "inf":
                toks.append(("num", math.inf))
            elif word == "nan":
                toks.append(("num", math.nan))
            else:
                toks.append(("id", word))
            continue
        if c.isdigit() or c == ".":
            j = i
            while j < n and (src[j].isdigit() or src[j] == "."):
                j += 1
            if j < n and src[j] in "eE":
                j += 1
                if j < n and src[j] in "+-":
                    j += 1
                while j < n and src[j].isdigit():
                    j += 1
            toks.append(("num", float(src[i:j])))
            i = j
            continue
        raise ValueError("lex error")
    toks.append(("end", None))
    return toks


class Parser:
    def __init__(self, toks):
        self.t = toks
        self.i = 0

    def cur(self):
        return self.t[self.i]

    def adv(self):
        self.i += 1

    def parse_expr(self):
        left = self.parse_term()
        while self.cur()[0] in ("+", "-"):
            op = self.cur()[0]
            self.adv()
            right = self.parse_term()
            left = Node("add" if op == "+" else "sub", a=left, b=right)
        return left

    def parse_term(self):
        left = self.parse_factor()
        while self.cur()[0] in ("*", "/"):
            op = self.cur()[0]
            self.adv()
            right = self.parse_factor()
            left = Node("mul" if op == "*" else "div", a=left, b=right)
        return left

    def parse_factor(self):
        if self.cur()[0] == "-":
            self.adv()
            inner = self.parse_factor()
            if inner.kind == "num":
                return Node("num", num=-inner.num)
            return Node("neg", a=inner)
        return self.parse_atom()

    def parse_atom(self):
        tok = self.cur()
        if tok[0] == "num":
            self.adv()
            return Node("num", num=tok[1])
        if tok[0] == "id":
            self.adv()
            return Node("var", name=tok[1])
        if tok[0] == "(":
            self.adv()
            e = self.parse_expr()
            if self.cur()[0] != ")":
                raise ValueError("expected )")
            self.adv()
            return e
        raise ValueError("parse error")


def parse(src):
    p = Parser(lex(src))
    e = p.parse_expr()
    if p.cur()[0] != "end":
        raise ValueError("trailing tokens")
    return e


def ieee_div(x, y):
    if y == 0.0:
        if math.isnan(x) or x == 0.0:
            return math.nan
        sign = math.copysign(1.0, x) * math.copysign(1.0, y)
        return math.inf if sign > 0 else -math.inf
    return x / y


def eval_bin(kind, x, y):
    if kind == "add":
        return x + y
    if kind == "sub":
        return x - y
    if kind == "mul":
        return x * y
    return ieee_div(x, y)


def is_neg_zero(n):
    return n.kind == "num" and n.num == 0.0 and math.copysign(1.0, n.num) < 0


def is_pos_zero(n):
    return n.kind == "num" and n.num == 0.0 and math.copysign(1.0, n.num) > 0


def is_one(n):
    return n.kind == "num" and n.num == 1.0


def fold(n):
    if n.kind in ("num", "var"):
        return n
    if n.kind == "neg":
        n.a = fold(n.a)
        if n.a.kind == "num":
            return Node("num", num=-n.a.num)
        if n.a.kind == "neg":
            return n.a.a
        return n
    n.a = fold(n.a)
    n.b = fold(n.b)
    a = n.a
    b = n.b
    if a.kind == "num" and b.kind == "num":
        return Node("num", num=eval_bin(n.kind, a.num, b.num))
    if n.kind == "add":
        if is_neg_zero(a):
            return b
        if is_neg_zero(b):
            return a
    elif n.kind == "sub":
        if is_pos_zero(b):
            return a
    elif n.kind == "mul":
        if is_one(a):
            return b
        if is_one(b):
            return a
    elif n.kind == "div":
        if is_one(b):
            return a
    return n


def num_key(v):
    if math.isnan(v):
        return ("num", "nan")
    return ("num", struct.pack(">d", v))


def canon(n):
    if n.kind == "num":
        return num_key(n.num)
    if n.kind == "var":
        return ("var", n.name)
    if n.kind == "neg":
        return ("neg", canon(n.a))
    return (n.kind, canon(n.a), canon(n.b))


def expected(program):
    return canon(fold(parse(program)))


def canon_of_output(text):
    return canon(parse(text.strip()))
