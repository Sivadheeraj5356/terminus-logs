"""Independent reference for the LCG keystream-recovery challenge.

Verifier-only. Given the public challenge text, it recovers the generator's
secret modulus, multiplier and increment from the published consecutive outputs
(the modulus is the gcd of the second-difference products; the multiplier and
increment then follow by modular linear algebra), advances the state past the
published run, rebuilds the keystream from the disclosed high-byte rule, and
XOR-decrypts the message. It never imports or observes candidate code, and uses
Python big integers so no intermediate overflows.
"""

from math import gcd


class ChallengeError(Exception):
    pass


def parse(text):
    width = w = outputs = ct = None
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        if "=" not in line:
            raise ChallengeError("bad line")
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip()
        if k == "width":
            width = int(v)
        elif k == "keystream_high_bytes":
            w = int(v)
        elif k == "outputs":
            outputs = [int(x) for x in v.split(",") if x.strip() != ""]
        elif k == "ciphertext":
            ct = bytes.fromhex(v)
        else:
            raise ChallengeError("unknown key " + k)
    if width is None or w is None or outputs is None or ct is None:
        raise ChallengeError("missing field")
    return width, w, outputs, ct


def recover_params(outputs):
    n = len(outputs)
    if n < 5:
        raise ChallengeError("too few outputs")
    d = [outputs[i + 1] - outputs[i] for i in range(n - 1)]
    g = 0
    for j in range(1, len(d) - 1):
        g = gcd(g, abs(d[j + 1] * d[j - 1] - d[j] * d[j]))
    if g < 2:
        raise ChallengeError("no modulus")
    m = g
    d0 = (outputs[1] - outputs[0]) % m
    a = (((outputs[2] - outputs[1]) % m) * pow(d0, -1, m)) % m
    c = (outputs[1] - a * outputs[0]) % m
    for i in range(n - 1):
        if (a * outputs[i] + c) % m != outputs[i + 1] % m:
            raise ChallengeError("recovered parameters do not reproduce outputs")
    return m, a, c


def decrypt(width, w, outputs, m, a, c, ct):
    sb = width // 8
    x = (a * (outputs[-1] % m) + c) % m
    ks = bytearray()
    while len(ks) < len(ct):
        ks += x.to_bytes(sb, "big")[:w]
        x = (a * x + c) % m
    return bytes(p ^ k for p, k in zip(ct, ks[: len(ct)]))


def solve_text(text):
    width, w, outputs, ct = parse(text)
    m, a, c = recover_params(outputs)
    return decrypt(width, w, outputs, m, a, c, ct)
