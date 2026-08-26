#!/usr/bin/env python3
"""Independent verifier-side oracle for msgsigward-go-rfc9421-signature-base-audit.

Verifier-only; never shipped into the agent environment. Reference verifier for
the RFC 9421 HTTP Message Signatures contract in docs/security-spec.md. Reads one
immutable request bundle carrying one *or more* labelled candidate signatures and
prints the canonical decision line:

    <verdict> <selector> <covered>

verdict in {verified, rejected}. For `verified`, <selector> is the label of the
accepted signature; for `rejected`, <selector> is the reason code. <covered> is
the comma-joined ordered list of covered component identifiers (serialised with
their parameters) that the selected signature authenticated, or "-" when the
decision is reached before any candidate is cryptographically trusted.

ed25519 is the RFC 8032 reference implementation (pure stdlib); HMAC-SHA256 is
stdlib hmac. No external crypto dependency, fully offline and deterministic.

This module is BOTH the reference oracle and the deterministic bundle generator,
so the corpus, the runtime-fresh anti-hardcoding bundles, and the graded truth
all come from one independent implementation.
"""

import base64
import hashlib
import hmac
import json
import os
import sys

# --------------------------------------------------------------------------- #
# ed25519 (RFC 8032 reference implementation, extended coordinates)           #
# --------------------------------------------------------------------------- #
_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493


def _modp_inv(x):
    return pow(x, _P - 2, _P)


_D = -121665 * _modp_inv(121666) % _P


def _sha512(s):
    return hashlib.sha512(s).digest()


def _sha512_modq(s):
    return int.from_bytes(_sha512(s), "little") % _Q


def _point_add(P, Q):
    A = (P[1] - P[0]) * (Q[1] - Q[0]) % _P
    B = (P[1] + P[0]) * (Q[1] + Q[0]) % _P
    C = 2 * P[3] * Q[3] * _D % _P
    Dd = 2 * P[2] * Q[2] % _P
    E, F, G, H = B - A, Dd - C, Dd + C, B + A
    return (E * F, G * H, F * G, E * H)


def _point_mul(s, P):
    Q = (0, 1, 1, 0)
    while s > 0:
        if s & 1:
            Q = _point_add(Q, P)
        P = _point_add(P, P)
        s >>= 1
    return Q


def _point_equal(P, Q):
    if (P[0] * Q[2] - Q[0] * P[2]) % _P != 0:
        return False
    if (P[1] * Q[2] - Q[1] * P[2]) % _P != 0:
        return False
    return True


_G_Y = 4 * _modp_inv(5) % _P


def _recover_x(y, sign):
    if y >= _P:
        return None
    x2 = (y * y - 1) * _modp_inv(_D * y * y + 1) % _P
    if x2 == 0:
        if sign:
            return None
        return 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = x * pow(2, (_P - 1) // 4, _P) % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_G_X = _recover_x(_G_Y, 0)
_G = (_G_X, _G_Y, 1, _G_X * _G_Y % _P)


def _point_compress(P):
    zinv = _modp_inv(P[2])
    x = P[0] * zinv % _P
    y = P[1] * zinv % _P
    return int.to_bytes(y | ((x & 1) << 255), 32, "little")


def _point_decompress(s):
    if len(s) != 32:
        return None
    y = int.from_bytes(s, "little")
    sign = y >> 255
    y &= (1 << 255) - 1
    x = _recover_x(y, sign)
    if x is None:
        return None
    return (x, y, 1, x * y % _P)


def _secret_expand(secret):
    h = _sha512(secret)
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 8
    a |= 1 << 254
    return a, h[32:]


def ed25519_public(secret):
    a, _ = _secret_expand(secret)
    return _point_compress(_point_mul(a, _G))


def ed25519_sign(secret, msg):
    a, prefix = _secret_expand(secret)
    A = _point_compress(_point_mul(a, _G))
    r = _sha512_modq(prefix + msg)
    R = _point_mul(r, _G)
    Rs = _point_compress(R)
    h = _sha512_modq(Rs + A + msg)
    s = (r + h * a) % _Q
    return Rs + int.to_bytes(s, 32, "little")


def ed25519_verify(public, msg, signature):
    if len(public) != 32 or len(signature) != 64:
        return False
    A = _point_decompress(public)
    if not A:
        return False
    Rs = signature[:32]
    R = _point_decompress(Rs)
    if not R:
        return False
    s = int.from_bytes(signature[32:], "little")
    if s >= _Q:
        return False
    h = _sha512_modq(Rs + public + msg)
    sB = _point_mul(s, _G)
    hA = _point_mul(h, A)
    return _point_equal(sB, _point_add(R, hA))


# --------------------------------------------------------------------------- #
# Small helpers                                                               #
# --------------------------------------------------------------------------- #
def _b64(b):
    return base64.b64encode(b).decode()


def _b64d(s):
    return base64.b64decode(s.encode())


def sha256_b64(b):
    return _b64(hashlib.sha256(b).digest())


def content_digest(body_bytes):
    return "sha-256=:" + sha256_b64(body_bytes) + ":"


class ParseError(Exception):
    pass


# --------------------------------------------------------------------------- #
# Structured-field-ish serialisation of a component identifier + params        #
# --------------------------------------------------------------------------- #
def _sf_string(s):
    """Serialise a string as an RFC 8941 sf-string (escape \\ and ")."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def serialize_component_id(name, params):
    """Canonical serialisation of a covered component identifier with its
    parameters, e.g. `"content-digest";bs` or `"@query-param";name="q"`.
    params is an ordered list of (key, value) where value is True (a bare
    boolean-true parameter, serialised without `=?1`) or a str."""
    out = _sf_string(name)
    for k, v in params:
        if v is True:
            out += ";" + k
        else:
            out += ";" + k + "=" + _sf_string(v)
    return out


# --------------------------------------------------------------------------- #
# Low-level quote/paren-aware splitters                                        #
# --------------------------------------------------------------------------- #
def _split_top(s, sep):
    """Split s on sep at top level, respecting "..." strings and (...) lists."""
    out = []
    depth = 0
    instr = False
    i = 0
    start = 0
    while i < len(s):
        c = s[i]
        if instr:
            if c == "\\":
                i += 2
                continue
            if c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
            elif c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
                if depth < 0:
                    raise ParseError("unbalanced )")
            elif c == sep and depth == 0:
                out.append(s[start:i])
                start = i + 1
        i += 1
    if instr or depth != 0:
        raise ParseError("unterminated string or list")
    out.append(s[start:])
    return out


def _split_ws(s):
    """Split an inner list body on spaces, respecting "..." strings."""
    out = []
    instr = False
    cur = ""
    i = 0
    while i < len(s):
        c = s[i]
        if instr:
            cur += c
            if c == "\\" and i + 1 < len(s):
                cur += s[i + 1]
                i += 2
                continue
            if c == '"':
                instr = False
        else:
            if c == '"':
                instr = True
                cur += c
            elif c == " ":
                if cur == "":
                    raise ParseError("double space in inner list")
                out.append(cur)
                cur = ""
            else:
                cur += c
        i += 1
    if instr:
        raise ParseError("unterminated string in inner list")
    if cur != "":
        out.append(cur)
    return out


def _unescape(s):
    out = ""
    i = 0
    while i < len(s):
        c = s[i]
        if c == "\\" and i + 1 < len(s):
            out += s[i + 1]
            i += 2
            continue
        out += c
        i += 1
    return out


def _parse_quoted(tok):
    """Parse a leading "..." from tok; return (unescaped, rest)."""
    if not tok.startswith('"'):
        raise ParseError("expected quoted string")
    i = 1
    while i < len(tok):
        c = tok[i]
        if c == "\\":
            i += 2
            continue
        if c == '"':
            return _unescape(tok[1:i]), tok[i + 1 :]
        i += 1
    raise ParseError("unterminated quoted string")


def _parse_params(rest):
    """Parse `;k` / `;k="v"` parameters into an ordered list of (k, val)."""
    params = []
    if rest == "":
        return params
    if not rest.startswith(";"):
        raise ParseError(f"expected parameters, got {rest!r}")
    for part in _split_top(rest[1:], ";"):
        if part == "":
            raise ParseError("empty parameter")
        if "=" in part:
            k, v = part.split("=", 1)
            if not (len(v) >= 2 and v[0] == '"' and v[-1] == '"'):
                raise ParseError(f"parameter {k} value not a string: {v!r}")
            uq, tail = _parse_quoted(v)
            if tail != "":
                raise ParseError("trailing junk after parameter value")
            params.append((k, uq))
        else:
            params.append((part, True))
    return params


def parse_component_id(tok):
    """Parse one inner-list member `"name"` + optional params."""
    name, rest = _parse_quoted(tok)
    params = _parse_params(rest)
    return name, params


# --------------------------------------------------------------------------- #
# Signature-Input / Signature dictionaries                                     #
# --------------------------------------------------------------------------- #
def parse_sig_params(params_str):
    """Parse a member's `;name=value` signature parameters (created/expires are
    integers, keyid/alg/nonce/tag are strings)."""
    out = {}
    if params_str == "":
        return out
    if not params_str.startswith(";"):
        raise ParseError("signature params must start with ;")
    for part in _split_top(params_str[1:], ";"):
        if "=" not in part:
            raise ParseError(f"bad signature param: {part!r}")
        k, v = part.split("=", 1)
        if k in ("created", "expires"):
            if not (v and (v.isdigit() or (v[0] == "-" and v[1:].isdigit()))):
                raise ParseError(f"{k} not an integer: {v!r}")
            out[k] = int(v)
        elif k in ("keyid", "alg", "nonce", "tag"):
            if len(v) < 2 or v[0] != '"' or v[-1] != '"':
                raise ParseError(f"{k} not a quoted string: {v!r}")
            uq, tail = _parse_quoted(v)
            if tail != "":
                raise ParseError("trailing junk after param value")
            out[k] = uq
        else:
            raise ParseError(f"unknown signature param: {k!r}")
    return out


def parse_signature_input(value):
    """Parse the Signature-Input dictionary into ordered candidates:
    a list of (label, ids, params, member_value) where ids is a list of
    (name, component-params), params is the signature-params dict, and
    member_value is the exact serialised `(...);params` used verbatim as the
    @signature-params component value for that label."""
    members = _split_top(value, ",")
    labels_seen = set()
    out = []
    for member in members:
        member = member.strip()
        if member == "":
            raise ParseError("empty dictionary member")
        if "=" not in member:
            raise ParseError("dictionary member has no '='")
        label, mval = member.split("=", 1)
        label = label.strip()
        if label == "" or " " in label:
            raise ParseError(f"bad label {label!r}")
        if label in labels_seen:
            raise ParseError(f"duplicate label {label!r}")
        labels_seen.add(label)
        mval = mval.strip()
        if not mval.startswith("("):
            raise ParseError("member value must be an inner list")
        close = mval.find(")")
        if close < 0:
            raise ParseError("inner list not closed")
        inner = mval[1:close]
        params_str = mval[close + 1 :]
        ids = []
        if inner.strip() != "":
            for tok in _split_ws(inner):
                ids.append(parse_component_id(tok))
        params = parse_sig_params(params_str)
        out.append((label, ids, params, mval))
    return out


def parse_signature(value):
    """Parse the Signature dictionary into {label: raw signature bytes}."""
    out = {}
    for member in _split_top(value, ","):
        member = member.strip()
        if member == "":
            raise ParseError("empty signature member")
        if "=" not in member:
            raise ParseError("signature member has no '='")
        label, sval = member.split("=", 1)
        label = label.strip()
        sval = sval.strip()
        if len(sval) < 2 or sval[0] != ":" or sval[-1] != ":":
            raise ParseError("signature not a byte sequence :b64:")
        try:
            out[label] = _b64d(sval[1:-1])
        except Exception as exc:  # noqa: BLE001
            raise ParseError(f"bad base64 signature: {exc}")
    return out


# --------------------------------------------------------------------------- #
# Component value derivation (with canonicalisation)                           #
# --------------------------------------------------------------------------- #
def pct_decode(s):
    """Percent-decode: %XX (hex) -> byte; '+' stays literal; a malformed % is
    left verbatim. Result decoded as UTF-8."""
    out = bytearray()
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "%" and i + 2 < n + 0 and i + 2 <= n - 1:
            hx = s[i + 1 : i + 3]
            try:
                out.append(int(hx, 16))
                i += 3
                continue
            except ValueError:
                pass
        out.append(ord(c) & 0xFF)
        i += 1
    return out.decode("utf-8", "replace")


def canon_authority(a):
    """@authority: lowercase; drop a trailing default :443 port."""
    a = a.lower()
    if a.endswith(":443"):
        a = a[: -len(":443")]
    return a


def _unfold_strip(line):
    """Remove obsolete line folding (a newline followed by SP/HTAB becomes one
    space) and strip leading/trailing SP/HTAB."""
    out = []
    i = 0
    n = len(line)
    while i < n:
        c = line[i]
        if c in "\r\n":
            j = i + 1
            if j < n and line[j] == "\n" and c == "\r":
                j += 1
            if j < n and line[j] in " \t":
                while j < n and line[j] in " \t":
                    j += 1
                out.append(" ")
                i = j
                continue
            # a bare newline not part of obs-fold is left as-is
            out.append(c)
            i += 1
            continue
        out.append(c)
        i += 1
    return "".join(out).strip(" \t")


def _field_lines(msg, name):
    v = msg["headers"][name]
    if isinstance(v, list):
        if not all(isinstance(x, str) for x in v):
            raise ParseError("multi-value header must be a list of strings")
        return v
    if isinstance(v, str):
        return [v]
    raise ParseError("header value must be a string or list of strings")


def field_value_plain(msg, name):
    return ", ".join(_unfold_strip(ln) for ln in _field_lines(msg, name))


def field_value_bs(msg, name):
    return ", ".join(
        ":" + _b64(_unfold_strip(ln).encode()) + ":" for ln in _field_lines(msg, name)
    )


def query_param_value(query, want):
    if query == "":
        raise ParseError("no query for @query-param")
    matches = []
    for pair in query.split("&"):
        if pair == "":
            continue
        if "=" in pair:
            k, v = pair.split("=", 1)
        else:
            k, v = pair, ""
        if pct_decode(k) == want:
            matches.append(pct_decode(v))
    if len(matches) != 1:
        raise ParseError(f"@query-param name={want!r} matched {len(matches)} params")
    return matches[0]


_DERIVED_NOPARAM = {"@method", "@authority", "@path", "@query"}


# --------------------------------------------------------------------------- #
# RFC 8941 structured-field canonicalisation for ;sf header components          #
# (bounded to a Dictionary of Integer/Token/String/Boolean bare items+params).  #
# --------------------------------------------------------------------------- #
_SF_KEY0 = set("abcdefghijklmnopqrstuvwxyz*")
_SF_KEY = _SF_KEY0 | set("0123456789_-.")
_SF_TOKEN0 = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ*")
_SF_TCHAR = (
    set("!#$%&'*+-.^_`|~:/0123456789")
    | set("abcdefghijklmnopqrstuvwxyz")
    | set("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
)


def _sf_skip_sp(s, i):
    while i < len(s) and s[i] in " \t":
        i += 1
    return i


def _sf_parse_key(s, i):
    if i >= len(s) or s[i] not in _SF_KEY0:
        raise ParseError("bad sf key")
    j = i
    while j < len(s) and s[j] in _SF_KEY:
        j += 1
    return s[i:j], j


def _sf_parse_bare(s, i):
    n = len(s)
    if i >= n:
        raise ParseError("empty sf bare item")
    c = s[i]
    if c == '"':
        j = i + 1
        out = []
        while j < n:
            ch = s[j]
            if ch == "\\":
                if j + 1 >= n or s[j + 1] not in ('"', "\\"):
                    raise ParseError("bad sf string escape")
                out.append(s[j + 1])
                j += 2
                continue
            if ch == '"':
                return ("string", "".join(out)), j + 1
            if not (0x20 <= ord(ch) <= 0x7E):
                raise ParseError("bad sf string char")
            out.append(ch)
            j += 1
        raise ParseError("unterminated sf string")
    if c == "?":
        if i + 1 < n and s[i + 1] in "01":
            return ("bool", s[i + 1] == "1"), i + 2
        raise ParseError("bad sf boolean")
    if c == "-" or c.isdigit():
        j = i + 1 if c == "-" else i
        k = j
        while k < n and s[k].isdigit():
            k += 1
        if k == j or (k - j) > 15 or (k < n and s[k] == "."):
            raise ParseError("bad sf integer")
        return ("int", int(s[i:k])), k
    if c in _SF_TOKEN0:
        j = i
        while j < n and s[j] in _SF_TCHAR:
            j += 1
        return ("token", s[i:j]), j
    raise ParseError(f"bad sf bare item {c!r}")


def _sf_parse_params(s, i):
    params = []
    n = len(s)
    while i < n and s[i] == ";":
        i += 1
        i = _sf_skip_sp(s, i)
        key, i = _sf_parse_key(s, i)
        if i < n and s[i] == "=":
            i += 1
            val, i = _sf_parse_bare(s, i)
        else:
            val = ("bool", True)
        params.append((key, val))
    return params, i


def sf_parse_dict(s):
    """Parse an RFC 8941 Dictionary of bare-item members into an ordered list of
    (key, value, params). value is ('int'|'token'|'string'|'bool', v)."""
    members = []
    keys = []
    i = _sf_skip_sp(s, 0)
    n = len(s)
    while i < n:
        key, i = _sf_parse_key(s, i)
        if i < n and s[i] == "=":
            i += 1
            val, i = _sf_parse_bare(s, i)
        else:
            val = ("bool", True)
        prm, i = _sf_parse_params(s, i)
        if key in keys:  # RFC 8941: later definition wins
            pos = keys.index(key)
            members[pos] = (key, val, prm)
        else:
            keys.append(key)
            members.append((key, val, prm))
        i = _sf_skip_sp(s, i)
        if i >= n:
            break
        if s[i] != ",":
            raise ParseError("expected , in sf dict")
        i += 1
        i = _sf_skip_sp(s, i)
        if i >= n:
            raise ParseError("trailing comma in sf dict")
    return members


def _sf_ser_bare(value):
    t, v = value
    if t == "int":
        return str(v)
    if t == "token":
        return v
    if t == "string":
        return '"' + v.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return "?1" if v else "?0"


def _sf_ser_params(params):
    out = ""
    for pk, pv in params:
        if pv == ("bool", True):
            out += ";" + pk
        else:
            out += ";" + pk + "=" + _sf_ser_bare(pv)
    return out


def sf_serialize_dict(members):
    parts = []
    for key, value, params in members:
        if value == ("bool", True):
            parts.append(key + _sf_ser_params(params))
        else:
            parts.append(key + "=" + _sf_ser_bare(value) + _sf_ser_params(params))
    return ", ".join(parts)


def field_value_sf(msg, name):
    return sf_serialize_dict(sf_parse_dict(field_value_plain(msg, name)))


def component_value(msg, name, params):
    """Resolve one covered component identifier (with parameters) to its
    signature-base value, or raise ParseError if it cannot be resolved."""
    if name.startswith("@"):
        if name in _DERIVED_NOPARAM:
            if params:
                raise ParseError(f"{name} takes no parameters")
            if name == "@method":
                return msg["method"]
            if name == "@authority":
                return canon_authority(msg["authority"])
            if name == "@path":
                p = msg["path"]
                return p if p != "" else "/"
            if name == "@query":
                return "?" + msg.get("query", "")
        if name == "@query-param":
            want = None
            for k, v in params:
                if k == "name" and isinstance(v, str):
                    want = v
                else:
                    raise ParseError(f"@query-param bad parameter {k!r}")
            if want is None:
                raise ParseError("@query-param requires a name parameter")
            return query_param_value(msg.get("query", ""), want)
        raise ParseError(f"unsupported derived component: {name}")
    # header component
    if name not in msg["headers"]:
        raise ParseError(f"covered header not present: {name}")
    bs = sf = False
    for k, v in params:
        if k == "bs" and v is True:
            bs = True
        elif k == "sf" and v is True:
            sf = True
        else:
            raise ParseError(f"header component bad parameter {k!r}")
    if bs and sf:
        raise ParseError("bs and sf are mutually exclusive")
    if sf:
        return field_value_sf(msg, name)
    return field_value_bs(msg, name) if bs else field_value_plain(msg, name)


def signature_base(msg, ids, member_value):
    lines = []
    for name, params in ids:
        lines.append(
            f"{serialize_component_id(name, params)}: {component_value(msg, name, params)}"
        )
    lines.append(f'"@signature-params": {member_value}')
    return "\n".join(lines).encode()


# --------------------------------------------------------------------------- #
# Structural validation (unevaluatable input -> non-zero exit)                 #
# --------------------------------------------------------------------------- #
def _require(cond, why):
    if not cond:
        raise ParseError(why)


def parse_case(case):
    _require(isinstance(case, dict), "top-level not an object")
    for k in ("keys", "now", "message"):
        _require(k in case, f"missing {k}")
    _require(
        isinstance(case["keys"], dict) and case["keys"], "keys must be non-empty object"
    )
    _require(
        isinstance(case["now"], int) and not isinstance(case["now"], bool),
        "now must be an integer",
    )
    msg = case["message"]
    _require(isinstance(msg, dict), "message not an object")
    for k in ("method", "authority", "path", "headers"):
        _require(k in msg, f"message missing {k}")
    _require(isinstance(msg["headers"], dict), "headers not an object")
    headers = msg["headers"]
    _require("signature-input" in headers, "missing signature-input header")
    _require("signature" in headers, "missing signature header")
    _require(
        isinstance(headers["signature-input"], str), "signature-input must be a string"
    )
    _require(isinstance(headers["signature"], str), "signature must be a string")
    candidates = parse_signature_input(headers["signature-input"])
    _require(len(candidates) >= 1, "no signatures")
    sigs = parse_signature(headers["signature"])
    parsed = []
    for label, ids, params, member_value in candidates:
        _require("keyid" in params, f"{label}: signature-params missing keyid")
        _require(label in sigs, f"{label}: no matching signature member")
        # every covered component must resolve (structural), else unevaluatable
        for name, cparams in ids:
            component_value(msg, name, cparams)
        parsed.append(
            {
                "label": label,
                "ids": ids,
                "params": params,
                "member_value": member_value,
                "sig": sigs[label],
            }
        )
    return {"keys": case["keys"], "now": case["now"], "msg": msg, "candidates": parsed}


# --------------------------------------------------------------------------- #
# Crypto verification under a bound algorithm                                  #
# --------------------------------------------------------------------------- #
def _verify_under(alg, key, base, sig):
    if alg == "ed25519":
        pub = bytes.fromhex(key["public"])
        return ed25519_verify(pub, base, sig)
    if alg == "hmac-sha256":
        secret = (
            bytes.fromhex(key["secret"])
            if "secret" in key
            else bytes.fromhex(key["public"])
        )
        return hmac.compare_digest(hmac.new(secret, base, hashlib.sha256).digest(), sig)
    raise ParseError(f"unsupported alg: {alg}")


def _body_bytes(msg):
    b = msg.get("body", "")
    return b.encode() if isinstance(b, str) else bytes(b)


REQUIRED_ALWAYS = ("@method", "@authority", "@path")

# Ordered acceptance stages. A candidate that fires stage N is rejected; a
# candidate that reaches ACCEPT_STAGE is verified. Higher stage == further
# progress through the policy.
STAGE = {
    "unknown_key": 1,
    "alg_mismatch": 2,
    "signature_invalid": 3,
    "coverage_inadequate": 4,
    "expired": 5,
    "not_yet_valid": 6,
    "digest_mismatch": 7,
}
ACCEPT_STAGE = 8


# --------------------------------------------------------------------------- #
# Per-candidate evaluation + cross-candidate selection                         #
# --------------------------------------------------------------------------- #
def eval_candidate(
    keys,
    now,
    msg,
    cand,
    *,
    authority_canon=True,
    canon_components=True,
    check_coverage=True,
    check_freshness=True,
    check_digest=True,
    bind_alg=True,
):
    """Evaluate one candidate; return (stage, verdict, reason, covered).

    The keyword flags exist so the "wrong analyzer" variants can disable a single
    obligation without duplicating the whole routine."""
    ids, params, member_value, sig = (
        cand["ids"],
        cand["params"],
        cand["member_value"],
        cand["sig"],
    )
    covered = ",".join(serialize_component_id(n, p) for n, p in ids)
    names = set(n for n, _ in ids)
    keyid = params.get("keyid")
    if keyid not in keys:
        return (STAGE["unknown_key"], "rejected", "unknown_key", "-")
    key = keys[keyid]
    bound = key["alg"]
    alg = params.get("alg")
    if bind_alg:
        if alg is not None and alg != bound:
            return (STAGE["alg_mismatch"], "rejected", "alg_mismatch", "-")
        use = alg if alg is not None else bound
    else:
        use = alg if alg is not None else bound
    base = _signature_base_variant(
        msg, ids, member_value, authority_canon, canon_components
    )
    if not _verify_under(use, key, base, sig):
        return (STAGE["signature_invalid"], "rejected", "signature_invalid", "-")
    if check_coverage:
        required = set(REQUIRED_ALWAYS)
        if _body_bytes(msg):
            required.add("content-digest")
        if not required.issubset(names):
            return (
                STAGE["coverage_inadequate"],
                "rejected",
                "coverage_inadequate",
                covered,
            )
    if check_freshness:
        if "expires" in params and now > params["expires"]:
            return (STAGE["expired"], "rejected", "expired", covered)
        if "created" in params and now < params["created"]:
            return (STAGE["not_yet_valid"], "rejected", "not_yet_valid", covered)
    if check_digest and "content-digest" in names:
        if field_value_plain(msg, "content-digest") != content_digest(_body_bytes(msg)):
            return (STAGE["digest_mismatch"], "rejected", "digest_mismatch", covered)
    return (ACCEPT_STAGE, "verified", "ok", covered)


def _signature_base_variant(msg, ids, member_value, authority_canon, canon_components):
    """Signature base with optional obligations disabled (for wrong analyzers)."""
    if authority_canon and canon_components:
        return signature_base(msg, ids, member_value)
    lines = []
    for name, params in ids:
        cid = serialize_component_id(name, params)
        if not canon_components:
            v = _component_value_naive(msg, name, params, authority_canon)
        elif not authority_canon and name == "@authority":
            v = msg["authority"]
        else:
            v = component_value(msg, name, params)
        lines.append(f"{cid}: {v}")
    lines.append(f'"@signature-params": {member_value}')
    return "\n".join(lines).encode()


def _component_value_naive(msg, name, params, authority_canon):
    """A 'plain header, verbatim derived' resolver: ignores ;bs, @query-param
    specialisation, obs-fold and (optionally) @authority canonicalisation."""
    if name.startswith("@"):
        if name == "@authority":
            return (
                canon_authority(msg["authority"])
                if authority_canon
                else msg["authority"]
            )
        if name == "@method":
            return msg["method"]
        if name == "@path":
            p = msg["path"]
            return p if p != "" else "/"
        if name == "@query":
            return "?" + msg.get("query", "")
        # @query-param treated as a plain (unresolved) join -> empty
        return ""
    v = msg["headers"].get(name, "")
    if isinstance(v, list):
        return ", ".join(x.strip() for x in v)
    return v.strip()


def select_default(results):
    """results: list of (label, stage, verdict, reason, covered). Accept the
    widest-coverage verifying candidate (tie: ascending label); otherwise report
    the furthest-progress candidate's reason (tie: ascending label)."""
    verified = [r for r in results if r[2] == "verified"]
    if verified:
        best = sorted(verified, key=lambda r: (-_covered_count(r[4]), r[0]))[0]
        return f"verified {best[0]} {best[4]}"
    best = sorted(results, key=lambda r: (-r[1], r[0]))[0]
    return f"rejected {best[3]} {best[4]}"


def _covered_count(covered):
    return 0 if covered == "-" else len(covered.split(","))


def verify_oracle(parsed, evalfn=None, selectfn=None):
    evalfn = evalfn or eval_candidate
    selectfn = selectfn or select_default
    keys, now, msg = parsed["keys"], parsed["now"], parsed["msg"]
    results = []
    for cand in parsed["candidates"]:
        stage, verdict, reason, covered = evalfn(keys, now, msg, cand)
        results.append((cand["label"], stage, verdict, reason, covered))
    return selectfn(results)


def line(case):
    """Top-level: structural error -> ParseError (CLI exits non-zero)."""
    parsed = parse_case(case)
    return verify_oracle(parsed)


# --------------------------------------------------------------------------- #
# Wrong analyzers (plausible mistakes; each must diverge on >=1 corpus case)    #
# --------------------------------------------------------------------------- #
def _mk_eval(**flags):
    def fn(keys, now, msg, cand):
        return eval_candidate(keys, now, msg, cand, **flags)

    return fn


def _select_first_verify(results):
    verified = [r for r in results if r[2] == "verified"]
    if verified:
        best = verified[0]  # BUG: declared order, not widest coverage
        return f"verified {best[0]} {best[4]}"
    best = sorted(results, key=lambda r: (-r[1], r[0]))[0]
    return f"rejected {best[3]} {best[4]}"


def _select_first_reason(results):
    verified = [r for r in results if r[2] == "verified"]
    if verified:
        best = sorted(verified, key=lambda r: (-_covered_count(r[4]), r[0]))[0]
        return f"verified {best[0]} {best[4]}"
    best = results[0]  # BUG: first candidate's reason, not furthest progress
    return f"rejected {best[3]} {best[4]}"


def _select_only_first(results):
    r = results[0]  # BUG: evaluates only the first candidate
    if r[2] == "verified":
        return f"verified {r[0]} {r[4]}"
    return f"rejected {r[3]} {r[4]}"


WRONG = {
    # single-obligation drops (per-candidate)
    "verify_only": (_mk_eval(check_coverage=False), select_default),
    "no_freshness": (_mk_eval(check_freshness=False), select_default),
    "digest_unchecked": (_mk_eval(check_digest=False), select_default),
    "no_alg_binding": (_mk_eval(bind_alg=False), select_default),
    "no_authority_canon": (_mk_eval(authority_canon=False), select_default),
    "naive_components": (_mk_eval(canon_components=False), select_default),
    # cross-candidate selection mistakes
    "first_verify": (eval_candidate, _select_first_verify),
    "first_reason": (eval_candidate, _select_first_reason),
    "only_first": (eval_candidate, _select_only_first),
}


def wrong_line(name, case):
    try:
        parsed = parse_case(case)
    except ParseError:
        return "PARSE_ERROR"
    evalfn, selectfn = WRONG[name]
    return verify_oracle(parsed, evalfn=evalfn, selectfn=selectfn)


# --------------------------------------------------------------------------- #
# Deterministic keyring                                                        #
# --------------------------------------------------------------------------- #
class Keyring:
    """Deterministic keys derived from a seed. Even indices -> ed25519 keys,
    odd indices -> hmac-sha256 keys. keyid is stable per (seed, index)."""

    def __init__(self, seed):
        self.seed = seed if isinstance(seed, bytes) else seed.encode()

    def _material(self, idx):
        return hashlib.sha256(self.seed + b"|key|" + str(idx).encode()).digest()

    def keyid(self, idx):
        return (
            "k-"
            + hashlib.sha256(self.seed + b"|id|" + str(idx).encode()).hexdigest()[:12]
        )

    def entry(self, idx):
        kid = self.keyid(idx)
        mat = self._material(idx)
        if idx % 2 == 0:
            pub = ed25519_public(mat)
            return kid, "ed25519", {"alg": "ed25519", "public": pub.hex()}, mat
        return kid, "hmac-sha256", {"alg": "hmac-sha256", "secret": mat.hex()}, mat


def _sign_base(alg, material, base):
    if alg == "ed25519":
        return ed25519_sign(material, base)
    return hmac.new(material, base, hashlib.sha256).digest()


# --------------------------------------------------------------------------- #
# Bundle builder (single- or multi-candidate)                                  #
# --------------------------------------------------------------------------- #
def _member_value(ids, created, expires, keyid, alg, extra_params=""):
    ids_ser = " ".join(serialize_component_id(n, p) for n, p in ids)
    tail = f"({ids_ser})"
    if created is not None:
        tail += f";created={created}"
    if expires is not None:
        tail += f";expires={expires}"
    tail += f';keyid="{keyid}"'
    if alg is not None:
        tail += f';alg="{alg}"'
    tail += extra_params
    return tail


def build_bundle(kr, idx, opts=None):
    """Construct a request bundle carrying one candidate signature (the default)
    or several (opts['candidates']).

    Single-candidate opts keys (backward compatible with the reduced task, plus
    new levers):
      method/authority/path/query/body     override message fields
      extra_headers={name: value|[values]}  add headers (value may be a list)
      covered=[(name, params), ...]         override the covered set
      add_covered=[(name, params), ...]     append to the default covered set
      omit=<name>                           drop a covered component by base name
      created_delta / expires_delta         shift freshness relative to now
      wrong_alg=True                        claim hmac on an ed25519 key + forge
      unknown_key=True                      point keyid at an absent id
      tamper_covered / tamper_uncovered     mutate a message field post-signing
      stale_digest=True                     mutate body after signing
      mutate_query=(name, newval)           change one query param post-signing
    Multi-candidate: opts['candidates'] is a list of the above per-candidate
    dicts sharing one message; opts may still carry message overrides + tampering.
    """
    opts = dict(opts or {})
    now = 1_700_000_000 + idx

    method = opts.get("method", ["GET", "POST", "PUT", "DELETE"][idx % 4])
    authority = opts.get("authority", f"svc{idx % 5}.example.com")
    path = opts.get("path", f"/api/v{idx % 3}/resource/{idx}")
    query = opts.get("query", "" if idx % 2 else f"page={idx}&sort=asc")
    body = opts.get(
        "body", "" if (idx % 3 == 0) else json.dumps({"n": idx, "op": "update"})
    )
    body_bytes = body.encode()

    headers = {"content-type": "application/json"}
    if body:
        headers["content-digest"] = content_digest(body_bytes)
    for hn, hv in opts.get("extra_headers", {}).items():
        headers[hn] = hv

    msg = {
        "method": method,
        "authority": authority,
        "path": path,
        "query": query,
        "headers": dict(headers),
        "body": body,
    }

    cand_specs = opts.get("candidates")
    if cand_specs is None:
        cand_specs = [opts]

    si_members = []
    sig_members = []
    for ci, cspec in enumerate(cand_specs):
        label = cspec.get("label", "sig1" if len(cand_specs) == 1 else f"sig{ci + 1}")
        kidx = cspec.get("key_index", idx + ci)
        # the alg-downgrade forge (wrong_alg) targets an ed25519 key (even index)
        if cspec.get("wrong_alg") and kidx % 2 == 1:
            kidx += 1
        kid, bound_alg, key_pub, material = kr.entry(kidx)

        # default covered set
        covered = [("@method", []), ("@authority", []), ("@path", [])]
        if query:
            covered.append(("@query", []))
        if body:
            covered.append(("content-digest", []))
        for hn in cspec.get("extra_cover_headers", []):
            covered.append(hn)
        covered = cspec.get("covered", covered + cspec.get("add_covered", []))
        if "omit" in cspec:
            covered = [(n, p) for (n, p) in covered if n != cspec["omit"]]

        created = now + cspec.get("created_delta", -60)
        expires = now + cspec.get("expires_delta", 300)
        keyid_decl = "k-missing-000000" if cspec.get("unknown_key") else kid
        alg_decl = "hmac-sha256" if cspec.get("wrong_alg") else bound_alg
        if cspec.get("omit_alg"):
            alg_decl = None

        member_value = _member_value(covered, created, expires, keyid_decl, alg_decl)
        si_members.append(f"{label}={member_value}")

        base = signature_base(msg, covered, member_value)
        if cspec.get("wrong_alg"):
            sig_bytes = hmac.new(
                bytes.fromhex(key_pub["public"]), base, hashlib.sha256
            ).digest()
        else:
            sig_bytes = _sign_base(bound_alg, material, base)
        sig_members.append(f"{label}=:{_b64(sig_bytes)}:")

        # this candidate's trusted key (multiple candidates union their keys)
        if not cspec.get("unknown_key"):
            headers_keys = opts.setdefault("_keys", {})
            headers_keys[kid] = key_pub

    msg["headers"]["signature-input"] = ", ".join(si_members)
    msg["headers"]["signature"] = ", ".join(sig_members)

    keys = dict(opts.get("_keys", {}))
    # ensure at least one key exists even if every candidate used unknown_key
    if not keys:
        kid, _, key_pub, _ = kr.entry(idx)
        keys[kid] = key_pub

    # Post-signing tampering (shared message; signatures stay fixed).
    _apply_tamper(msg, opts, query)

    return {"keys": keys, "now": now, "message": msg}


def _apply_tamper(msg, opts, orig_query):
    if "tamper_covered" in opts:
        f = opts["tamper_covered"]
        if f == "@method":
            msg["method"] = "TRACE"
        elif f == "@path":
            msg["path"] = msg["path"] + "/evil"
        elif f == "@authority":
            msg["authority"] = "attacker.example.net"
        elif f == "@query":
            msg["query"] = msg["query"] + "&admin=1"
    if "tamper_uncovered" in opts:
        f = opts["tamper_uncovered"]
        if f == "@method":
            msg["method"] = "DELETE" if msg["method"] != "DELETE" else "GET"
        elif f == "@path":
            msg["path"] = msg["path"] + "/shadow"
        elif f == "@authority":
            msg["authority"] = "evil.example.net"
    if "mutate_query" in opts:
        name, newval = opts["mutate_query"]
        pairs = []
        for pair in msg["query"].split("&"):
            k = pair.split("=", 1)[0]
            if k == name:
                pairs.append(f"{name}={newval}")
            else:
                pairs.append(pair)
        msg["query"] = "&".join(pairs)
    if opts.get("stale_digest"):
        msg["body"] = msg["body"] + "TAMPER"


# --------------------------------------------------------------------------- #
# Deterministic corpus                                                         #
# --------------------------------------------------------------------------- #
def build_corpus(seed):
    kr = Keyring(seed)
    cases = []
    idx = 10

    def add(name, i, opts, expect_prefix=None):
        case = build_bundle(kr, i, opts)
        got = line(case)
        if expect_prefix is not None:
            assert got.split()[0] == expect_prefix, (
                f"{name}: oracle {got!r} != {expect_prefix}"
            )
        cases.append({"name": name, "case": case, "expected": got})

    # --- genuine single-signature verifications across methods/algs/body/query
    for i in range(20):
        add(f"genuine_{i:02d}", idx, {}, "verified")
        idx += 1
    # hmac genuine (odd key index)
    for i in range(8):
        odd = idx if idx % 2 == 1 else idx + 1
        add(f"hmac_genuine_{i}", odd, {}, "verified")
        idx = odd + 1
    # empty body (content-digest not required)
    for i in range(5):
        add(f"empty_body_{i}", idx, {"body": ""}, "verified")
        idx += 1

    # --- coverage adequacy
    for cid in ("@method", "@authority", "@path", "content-digest"):
        add(
            f"undercover_{cid.strip('@')}",
            idx,
            {"omit": cid, "body": '{"x":1}'},
            "rejected",
        )
        idx += 1
    for cid in ("@method", "@authority", "@path"):
        add(
            f"tamper_uncov_{cid.strip('@')}",
            idx,
            {"omit": cid, "tamper_uncovered": cid},
            "rejected",
        )
        idx += 1

    # --- tamper a covered field -> signature must fail
    for cid in ("@method", "@path", "@authority", "@query"):
        o = {"tamper_covered": cid}
        if cid == "@query":
            o["query"] = "page=1&sort=asc"
        add(f"tamper_cov_{cid.strip('@')}", idx, o, "rejected")
        idx += 1

    # --- freshness
    for d in (-1, -100, -3600):
        add(f"expired_{abs(d)}", idx, {"expires_delta": d}, "rejected")
        idx += 1
    for d in (1, 50, 600):
        add(f"notyet_{d}", idx, {"created_delta": d}, "rejected")
        idx += 1
    for i in range(3):
        add(f"boundary_created_{i}", idx, {"created_delta": 0}, "verified")
        idx += 1
        add(f"boundary_expires_{i}", idx, {"expires_delta": 0}, "verified")
        idx += 1

    # --- body binding
    for i in range(5):
        add(
            f"stale_digest_{i}",
            idx,
            {"body": json.dumps({"v": idx}), "stale_digest": True},
            "rejected",
        )
        idx += 1

    # --- algorithm binding / downgrade
    for i in range(4):
        even = idx if idx % 2 == 0 else idx + 1
        add(f"alg_downgrade_{i}", even, {"wrong_alg": True}, "rejected")
        idx = even + 1

    # --- unknown key
    for i in range(3):
        add(f"unknown_key_{i}", idx, {"unknown_key": True}, "rejected")
        idx += 1

    # --- multi-value header + obsolete line folding (plain join with ", ")
    for i in range(4):
        hv = [f"a{idx}", f"b {idx}", f"c\n  {idx}"]  # last has obs-fold
        add(
            f"multivalue_{i}",
            idx,
            {"extra_headers": {"x-fwd": hv}, "extra_cover_headers": [("x-fwd", [])]},
            "verified",
        )
        idx += 1

    # --- byte-sequence-wrapped header (;bs), multi-value
    for i in range(4):
        hv = [f"v{idx}=1, q", f"w{idx}"]  # a value containing a comma; bs makes it safe
        add(
            f"bs_header_{i}",
            idx,
            {
                "extra_headers": {"x-bs": hv},
                "extra_cover_headers": [("x-bs", [("bs", True)])],
            },
            "verified",
        )
        idx += 1
    # tamper a bs-covered value -> signature must fail
    add(
        "bs_tamper",
        idx,
        {
            "extra_headers": {"x-bs": ["one", "two"]},
            "extra_cover_headers": [("x-bs", [("bs", True)])],
            "tamper_covered": "@path",
        },
        "rejected",
    )
    idx += 1

    # --- strict Structured-Field (;sf) canonicalisation of a Dictionary value.
    # The signer signs over the CANONICAL serialisation; each raw form below is
    # non-canonical, so a verifier that uses the field value verbatim fails.
    sf_raws = [
        "a=007,  b=widget",
        "flag=?1, count=-003;fresh=?1",
        'label="a\\"b",  kind=token9',
        "x=00, y=?0, z=hello",
        "p=1;q=?1;r=2, s=abc",
        "m=042,   n=tok;a=07",
        "only=?1",
        'note="  x  ",k=9',
    ]
    for i, raw in enumerate(sf_raws):
        add(
            f"sf_dict_{i}",
            idx,
            {
                "extra_headers": {"x-dict": raw},
                "extra_cover_headers": [("x-dict", [("sf", True)])],
            },
            "verified",
        )
        idx += 1
    # tamper an sf-covered dict value (change a covered field) -> signature fails
    add(
        "sf_tamper",
        idx,
        {
            "extra_headers": {"x-dict": "a=1, b=2"},
            "extra_cover_headers": [("x-dict", [("sf", True)])],
            "tamper_covered": "@authority",
        },
        "rejected",
    )
    idx += 1

    # --- @authority canonicalisation (uppercase host + default port)
    for i, host in enumerate(
        ("SVC.Example.COM", "Svc.Example.Com:443", "API.SVC.example.com")
    ):
        add(f"authority_canon_{i}", idx, {"authority": host}, "verified")
        idx += 1

    # --- @path empty -> "/"
    add("path_empty", idx, {"path": ""}, "verified")
    idx += 1

    # --- @query-param covered, percent-decoded
    for i in range(4):
        q = f"user=alice%20smith&role=admin&id={idx}"
        add(
            f"qparam_{i}",
            idx,
            {
                "query": q,
                "add_covered": [
                    ("@query-param", [("name", "user")]),
                    ("@query-param", [("name", "role")]),
                ],
            },
            "verified",
        )
        idx += 1
    # mutate a COVERED query-param -> signature must fail
    add(
        "qparam_tamper_covered",
        idx,
        {
            "query": f"user=bob&role=admin&id={idx}",
            "add_covered": [("@query-param", [("name", "role")])],
            "mutate_query": ("role", "superadmin"),
        },
        "rejected",
    )
    idx += 1
    # mutate an UNCOVERED query-param, @query not covered -> still verified
    add(
        "qparam_uncovered_ok",
        idx,
        {
            "query": f"user=carol&role=admin&id={idx}",
            "covered": [
                ("@method", []),
                ("@authority", []),
                ("@path", []),
                ("@query-param", [("name", "user")]),
            ],
            "mutate_query": ("role", "guest"),
            "body": "",
        },
        "verified",
    )
    idx += 1

    # --- MULTIPLE SIGNATURES ------------------------------------------------ #
    # two verifying candidates with different coverage -> widest wins
    add(
        "multisig_widest",
        idx,
        {
            "query": "a=1&b=2",
            "candidates": [
                {
                    "label": "narrow",
                    "key_index": idx,
                    "covered": [("@method", []), ("@authority", []), ("@path", [])],
                    "body": "",
                },
                {
                    "label": "wide",
                    "key_index": idx,
                    "covered": [
                        ("@method", []),
                        ("@authority", []),
                        ("@path", []),
                        ("@query", []),
                    ],
                    "body": "",
                },
            ],
            "body": "",
        },
        "verified",
    )
    idx += 1
    # a genuine signature stapled behind a broken decoy -> accept the genuine one
    add(
        "multisig_decoy_before_genuine",
        idx,
        {
            "candidates": [
                {"label": "decoy", "key_index": idx, "unknown_key": True},
                {"label": "real", "key_index": idx},
            ],
        },
        "verified",
    )
    idx += 1
    # all candidates reject at different stages -> report FURTHEST progress
    add(
        "multisig_furthest_reason",
        idx,
        {
            "candidates": [
                {"label": "aaa", "key_index": idx, "unknown_key": True},  # stage 1
                {
                    "label": "bbb",
                    "key_index": idx,
                    "expires_delta": -50,
                },  # stage 5 (expired)
            ],
        },
        "rejected",
    )
    idx += 1
    # first label fails shallow, second deeper, plus label tie ordering
    add(
        "multisig_shallow_first",
        idx,
        {
            "candidates": [
                {"label": "zzz", "key_index": idx, "expires_delta": -10},  # stage 5
                {"label": "mmm", "key_index": idx, "wrong_alg": True},  # stage 3
            ],
        },
        "rejected",
    )
    idx += 1
    # three candidates: two verify (widest tie broken by label), one rejects
    add(
        "multisig_three",
        idx,
        {
            "query": "x=9",
            "body": "",
            "candidates": [
                {
                    "label": "beta",
                    "key_index": idx,
                    "covered": [
                        ("@method", []),
                        ("@authority", []),
                        ("@path", []),
                        ("@query", []),
                    ],
                    "body": "",
                },
                {
                    "label": "alpha",
                    "key_index": idx,
                    "covered": [
                        ("@method", []),
                        ("@authority", []),
                        ("@path", []),
                        ("@query", []),
                    ],
                    "body": "",
                },
                {"label": "gamma", "key_index": idx, "expires_delta": -5, "body": ""},
            ],
        },
        "verified",
    )
    idx += 1

    return cases


# --------------------------------------------------------------------------- #
# Shipped examples (a distinct seed; small, illustrate the format + features)   #
# --------------------------------------------------------------------------- #
def build_examples(seed):
    kr = Keyring(seed)
    out = []

    def add(name, idx, opts):
        case = build_bundle(kr, idx, opts)
        out.append({"name": name, "case": case, "expected": line(case)})

    # Six shipped examples keep environment/ within the "minimal" file-count band
    # while illustrating single/multi-signature verification and each rejection.
    add("verified-ed25519", 2, {})  # even index -> ed25519
    add(
        "verified-query-param",
        4,
        {
            "query": "user=alice%20smith&id=4",
            "add_covered": [("@query-param", [("name", "user")])],
        },
    )
    add(
        "verified-multi-signature",
        6,
        {
            "query": "a=1",
            "body": "",
            "candidates": [
                {
                    "label": "edge",
                    "key_index": 6,
                    "covered": [("@method", []), ("@authority", []), ("@path", [])],
                    "body": "",
                },
                {
                    "label": "gateway",
                    "key_index": 6,
                    "covered": [
                        ("@method", []),
                        ("@authority", []),
                        ("@path", []),
                        ("@query", []),
                    ],
                    "body": "",
                },
            ],
        },
    )
    add("rejected-alg-downgrade", 8, {"wrong_alg": True})
    add("rejected-expired", 9, {"expires_delta": -120})
    add("rejected-undercovered", 10, {"omit": "@path", "body": '{"x":1}'})
    return out


# --------------------------------------------------------------------------- #
# Audit task: the shipped verifier has planted defects. Each defect is exposed  #
# by a witness bundle on which the shipped binary's decision diverges from this #
# independent oracle with a distinct (oracle, shipped) signature.               #
# --------------------------------------------------------------------------- #
# (slug, oracle-decision prefix, shipped-decision prefix)
AUDIT_DEFECTS = [
    ("coverage_authority", "rejected coverage_inadequate", "verified"),
    ("alg_binding", "rejected alg_mismatch", "verified"),
    ("digest_recompute", "rejected digest_mismatch", "verified"),
    ("freshness_expired", "rejected expired", "verified"),
    ("freshness_notyet", "rejected not_yet_valid", "verified"),
    ("base_whitespace", "verified", "rejected signature_invalid"),
    ("selection_reason", "rejected expired", "rejected unknown_key"),
]


def classify_divergence(oracle_line, shipped_line):
    """Return the slug of the defect a (oracle, shipped) decision pair exposes,
    or None if the pair is not a recognised defect signature."""
    for slug, o_pre, s_pre in AUDIT_DEFECTS:
        if oracle_line.startswith(o_pre) and shipped_line.startswith(s_pre):
            return slug
    return None


def build_audit_witnesses(seed):
    kr = Keyring(seed)
    out = []

    def add(defect, idx, opts):
        case = build_bundle(kr, idx, opts)
        out.append({"defect": defect, "witness": case, "oracle": line(case)})

    add("coverage_authority", 10, {"omit": "@authority", "body": ""})
    add("alg_binding", 12, {"wrong_alg": True})
    add("digest_recompute", 13, {"body": '{"amt":5}', "stale_digest": True})
    add("freshness_expired", 14, {"expires_delta": -100})
    add("freshness_notyet", 15, {"created_delta": 100})
    add(
        "base_whitespace",
        16,
        {
            "extra_headers": {"x-note": "a  b   c"},
            "extra_cover_headers": [("x-note", [])],
        },
    )
    add(
        "selection_reason",
        17,
        {
            "candidates": [
                {"label": "aaa", "key_index": 17, "unknown_key": True},
                {"label": "bbb", "key_index": 17, "expires_delta": -500},
            ]
        },
    )
    return out


# --------------------------------------------------------------------------- #
# CLI + corpus emission                                                        #
# --------------------------------------------------------------------------- #
def _emit(directory, seed):
    os.makedirs(directory, exist_ok=True)
    # clear old vectors
    for d in os.listdir(directory):
        p = os.path.join(directory, d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                os.remove(os.path.join(p, f))
            os.rmdir(p)
    cases = build_corpus(seed)
    for c in cases:
        d = os.path.join(directory, c["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "input.json"), "w") as fh:
            json.dump(c["case"], fh, indent=2, sort_keys=True)
            fh.write("\n")
        with open(os.path.join(d, "expected"), "w") as fh:
            fh.write(c["expected"] + "\n")
    return len(cases)


def _emit_examples(directory, seed):
    os.makedirs(directory, exist_ok=True)
    for d in os.listdir(directory):
        p = os.path.join(directory, d)
        if os.path.isdir(p):
            for f in os.listdir(p):
                os.remove(os.path.join(p, f))
            os.rmdir(p)
    exs = build_examples(seed)
    for c in exs:
        d = os.path.join(directory, c["name"])
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "input.json"), "w") as fh:
            json.dump(c["case"], fh, indent=2, sort_keys=True)
            fh.write("\n")
        with open(os.path.join(d, "expected"), "w") as fh:
            fh.write(c["expected"] + "\n")
    return len(exs)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--emit-corpus":
        n = _emit(sys.argv[2], b"msgsigward-corpus-seed-9421")
        sys.stderr.write(f"emitted {n} vectors to {sys.argv[2]}\n")
    elif len(sys.argv) == 3 and sys.argv[1] == "--emit-examples":
        n = _emit_examples(sys.argv[2], b"msgsigward-examples-seed-9421")
        sys.stderr.write(f"emitted {n} examples to {sys.argv[2]}\n")
    elif len(sys.argv) == 3 and sys.argv[1] == "--emit-findings":
        ws = build_audit_witnesses(b"msgsigward-oracle-findings-seed")
        findings = [{"defect": w["defect"], "witness": w["witness"]} for w in ws]
        with open(sys.argv[2], "w") as fh:
            json.dump({"findings": findings}, fh, indent=2, sort_keys=True)
            fh.write("\n")
        sys.stderr.write(f"emitted {len(findings)} findings to {sys.argv[2]}\n")
    elif len(sys.argv) == 2:
        with open(sys.argv[1], "rb") as fh:
            data = json.loads(fh.read())
        try:
            sys.stdout.write(line(data) + "\n")
        except ParseError as exc:
            sys.stderr.write(f"unevaluatable: {exc}\n")
            sys.exit(2)
    else:
        sys.stderr.write("usage: oracle.py <input.json> | --emit-corpus <dir>\n")
        sys.exit(2)
