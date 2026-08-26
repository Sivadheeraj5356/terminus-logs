"""Independent reference regex matcher over the rsx grammar subset.

This is a backtracking matcher used only to derive ground-truth language
membership for verification. It does not build automata; it is deliberately a
different algorithm from the program under test.
"""


class ParseError(Exception):
    pass


NAMED = {
    "digit": list(range(0x30, 0x3A)),
    "lower": list(range(0x61, 0x7B)),
    "upper": list(range(0x41, 0x5B)),
    "alpha": list(range(0x61, 0x7B)) + list(range(0x41, 0x5B)),
    "alnum": list(range(0x61, 0x7B)) + list(range(0x41, 0x5B)) + list(range(0x30, 0x3A)),
    "space": [0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x20],
    "hexdigit": list(range(0x30, 0x3A)) + list(range(0x41, 0x47)) + list(range(0x61, 0x67)),
    "punct": list(range(0x21, 0x30)) + list(range(0x3A, 0x41)) + list(range(0x5B, 0x61)) + list(range(0x7B, 0x7F)),
}

SIMPLE_ESC = {
    ord("n"): 0x0A,
    ord("t"): 0x09,
    ord("r"): 0x0D,
    ord("f"): 0x0C,
    ord("v"): 0x0B,
    ord("0"): 0x00,
    ord("\\"): 0x5C,
}

OUT_LIT = set(b".^$*+?()[]{}|")


class P:
    def __init__(self, data):
        self.b = data
        self.i = 0

    def peek(self, off=0):
        j = self.i + off
        if j < len(self.b):
            return self.b[j]
        return None

    def bump(self):
        c = self.peek()
        if c is not None:
            self.i += 1
        return c

    def eat(self, c):
        if self.peek() == c:
            self.i += 1
            return True
        return False

    def eof(self):
        return self.i >= len(self.b)


def hexv(c):
    if c is None:
        raise ParseError("hex")
    if 0x30 <= c <= 0x39:
        return c - 0x30
    if 0x61 <= c <= 0x66:
        return c - 0x61 + 10
    if 0x41 <= c <= 0x46:
        return c - 0x41 + 10
    raise ParseError("hex")


def parse(pattern_bytes):
    p = P(pattern_bytes)
    node = parse_alt(p)
    if not p.eof():
        raise ParseError("trailing")
    return node


def parse_alt(p):
    branches = [parse_concat(p)]
    while p.eat(ord("|")):
        branches.append(parse_concat(p))
    if len(branches) == 1:
        return branches[0]
    return ("alt", branches)


def parse_concat(p):
    items = []
    while True:
        c = p.peek()
        if c is None or c == ord("|") or c == ord(")"):
            break
        atom = parse_atom(p)
        atom = apply_reps(p, atom)
        items.append(atom)
    if not items:
        return ("empty",)
    if len(items) == 1:
        return items[0]
    return ("concat", items)


def apply_reps(p, node):
    while True:
        c = p.peek()
        if c == ord("*"):
            p.bump()
            node = ("star", node)
        elif c == ord("+"):
            p.bump()
            node = ("plus", node)
        elif c == ord("?"):
            p.bump()
            node = ("opt", node)
        elif c == ord("{"):
            r = try_counted(p)
            if r is None:
                break
            m, n = r
            node = expand_counted(node, m, n)
        else:
            break
    return node


def read_num(p):
    start = p.i
    val = 0
    while True:
        c = p.peek()
        if c is not None and 0x30 <= c <= 0x39:
            val = val * 10 + (c - 0x30)
            p.bump()
        else:
            break
    if p.i == start:
        return None
    return val


def try_counted(p):
    save = p.i
    p.bump()
    m = read_num(p)
    if m is None:
        p.i = save
        return None
    if p.eat(ord("}")):
        if m > 1024:
            raise ParseError("count")
        return (m, m)
    if p.eat(ord(",")):
        if p.eat(ord("}")):
            if m > 1024:
                raise ParseError("count")
            return (m, None)
        n = read_num(p)
        if n is None:
            p.i = save
            return None
        if not p.eat(ord("}")):
            p.i = save
            return None
        if m > n:
            raise ParseError("count order")
        if n > 1024:
            raise ParseError("count")
        return (m, n)
    p.i = save
    return None


def expand_counted(node, m, n):
    items = [node] * m
    if n is None:
        items = list(items) + [("star", node)]
    else:
        extra = n - m
        opt = ("empty",)
        for _ in range(extra):
            if opt == ("empty",):
                opt = ("opt", node)
            else:
                opt = ("opt", ("concat", [node, opt]))
        items = list(items)
        if opt != ("empty",):
            items.append(opt)
    if not items:
        return ("empty",)
    if len(items) == 1:
        return items[0]
    return ("concat", items)


def parse_atom(p):
    c = p.peek()
    if c == ord("("):
        p.bump()
        inner = parse_alt(p)
        if not p.eat(ord(")")):
            raise ParseError("group")
        return inner
    if c == ord("["):
        return ("class", parse_class(p))
    if c == ord("."):
        p.bump()
        s = set(range(256))
        s.discard(0x0A)
        return ("class", s)
    if c == ord("^"):
        p.bump()
        return ("astart",)
    if c == ord("$"):
        p.bump()
        return ("aend",)
    if c == ord("\\"):
        return ("byte", parse_escape(p))
    if c in (ord("*"), ord("+"), ord("?")):
        raise ParseError("rep no atom")
    if c in (ord(")"), ord("]"), ord("}")):
        raise ParseError("close")
    if c == ord("|"):
        raise ParseError("alt")
    if c is None:
        raise ParseError("eof")
    p.bump()
    return ("byte", c)


def parse_escape(p):
    p.bump()
    c = p.bump()
    if c is None:
        raise ParseError("esc")
    if c in SIMPLE_ESC:
        return SIMPLE_ESC[c]
    if c in OUT_LIT:
        return c
    if c == ord("x"):
        hi = p.bump()
        lo = p.bump()
        return hexv(hi) * 16 + hexv(lo)
    raise ParseError("esc")


def parse_class_escape(p):
    p.bump()
    c = p.bump()
    if c is None:
        raise ParseError("esc")
    if c in SIMPLE_ESC:
        return SIMPLE_ESC[c]
    if c in (ord("]"), ord("^"), ord("-")):
        return c
    if c == ord("x"):
        hi = p.bump()
        lo = p.bump()
        return hexv(hi) * 16 + hexv(lo)
    raise ParseError("esc")


def parse_class(p):
    if not p.eat(ord("[")):
        raise ParseError("class")
    negate = p.eat(ord("^"))
    s = set()
    first = True
    while True:
        c = p.peek()
        if c is None:
            raise ParseError("class eof")
        if c == ord("]"):
            p.bump()
            break
        if c == ord("-") and p.peek(1) == ord("-") and p.peek(2) == ord("["):
            p.bump()
            p.bump()
            sub = parse_class(p)
            s -= sub
            first = False
            continue
        if c == ord("&") and p.peek(1) == ord("&") and p.peek(2) == ord("["):
            p.bump()
            p.bump()
            sub = parse_class(p)
            s &= sub
            first = False
            continue
        if c == ord("[") and p.peek(1) == ord(":"):
            s |= set(parse_named(p))
            first = False
            continue
        lo = class_atom(p)
        is_last_dash = lo == ord("-") and p.peek() == ord("]")
        if lo == ord("-") and (first or is_last_dash):
            s.add(ord("-"))
            first = False
            continue
        if (
            p.peek() == ord("-")
            and p.peek(1) is not None
            and p.peek(1) != ord("]")
            and not (p.peek(1) == ord("-") and p.peek(2) == ord("["))
        ):
            p.bump()
            hi = class_atom(p)
            if lo > hi:
                raise ParseError("range")
            for b in range(lo, hi + 1):
                s.add(b)
        else:
            s.add(lo)
        first = False
    if negate:
        s = set(range(256)) - s
    return s


def class_atom(p):
    c = p.peek()
    if c == ord("\\"):
        return parse_class_escape(p)
    if c is None:
        raise ParseError("class eof")
    return p.bump()


def parse_named(p):
    p.bump()
    p.bump()
    name = bytearray()
    while True:
        c = p.peek()
        if c == ord(":") and p.peek(1) == ord("]"):
            p.bump()
            p.bump()
            break
        if c is not None and 0x61 <= c <= 0x7A:
            name.append(c)
            p.bump()
        else:
            raise ParseError("named")
    key = name.decode("ascii")
    if key not in NAMED:
        raise ParseError("named unknown")
    return NAMED[key]


def strip_anchors(node):
    if node[0] == "astart":
        return True, False, ("empty",)
    if node[0] == "aend":
        return False, True, ("empty",)
    if node[0] == "concat":
        st = False
        en = False
        out = []
        for it in node[1]:
            a, b, s2 = strip_anchors(it)
            st = st or a
            en = en or b
            if s2 != ("empty",):
                out.append(s2)
        if not out:
            return st, en, ("empty",)
        if len(out) == 1:
            return st, en, out[0]
        return st, en, ("concat", out)
    return False, False, node


def match_set(node, data, i):
    t = node[0]
    if t == "empty":
        yield i
    elif t == "byte":
        if i < len(data) and data[i] == node[1]:
            yield i + 1
    elif t == "class":
        if i < len(data) and data[i] in node[1]:
            yield i + 1
    elif t == "concat":
        def rec(k, pos):
            if k == len(node[1]):
                yield pos
                return
            for nxt in match_set(node[1][k], data, pos):
                yield from rec(k + 1, nxt)
        yield from rec(0, i)
    elif t == "alt":
        for br in node[1]:
            yield from match_set(br, data, i)
    elif t == "opt":
        yield i
        yield from match_set(node[1], data, i)
    elif t == "star":
        seen = set()

        def rec(pos):
            yield pos
            for nxt in match_set(node[1], data, pos):
                if nxt != pos and nxt not in seen:
                    seen.add(nxt)
                    yield from rec(nxt)
        yield from rec(i)
    elif t == "plus":
        for nxt in match_set(node[1], data, i):
            seen = set([nxt])

            def rec(pos):
                yield pos
                for n2 in match_set(node[1], data, pos):
                    if n2 != pos and n2 not in seen:
                        seen.add(n2)
                        yield from rec(n2)
            yield from rec(nxt)
    elif t in ("astart", "aend"):
        yield i
    else:
        raise ParseError("node")


def full_match(pattern_bytes, data):
    """Whole-string membership using the anchor-free core, as compile reports."""
    node = parse(pattern_bytes)
    _, _, core = strip_anchors(node)
    for end in match_set(core, data, 0):
        if end == len(data):
            return True
    return False


def is_valid(pattern_bytes):
    try:
        parse(pattern_bytes)
        return True
    except ParseError:
        return False
