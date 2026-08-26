"""Independent TZif reader used by the verifier. Parses, it does not assume."""

import struct


class TzifError(Exception):
    pass


class Block:
    def __init__(self, transitions, indices, types, chars, isstd, isut):
        self.transitions = transitions
        self.indices = indices
        self.types = types
        self.chars = chars
        self.isstd = isstd
        self.isut = isut

    def abbrev(self, desigidx):
        end = self.chars.index(b"\x00", desigidx)
        return self.chars[desigidx:end].decode("ascii")


class Tzif:
    def __init__(self, version, v1, v2, footer):
        self.version = version
        self.v1 = v1
        self.v2 = v2
        self.footer = footer


def _header(buf, pos):
    if buf[pos:pos + 4] != b"TZif":
        raise TzifError("bad magic at %d" % pos)
    version = buf[pos + 4:pos + 5]
    if buf[pos + 5:pos + 20] != b"\x00" * 15:
        raise TzifError("reserved octets are not zero")
    counts = struct.unpack(">6I", buf[pos + 20:pos + 44])
    return version, counts, pos + 44


def _block(buf, pos, counts, width):
    isutcnt, isstdcnt, leapcnt, timecnt, typecnt, charcnt = counts
    fmt = ">q" if width == 8 else ">i"
    transitions = [struct.unpack(fmt, buf[pos + i * width:pos + (i + 1) * width])[0]
                   for i in range(timecnt)]
    pos += timecnt * width
    indices = list(buf[pos:pos + timecnt])
    pos += timecnt
    types = []
    for _ in range(typecnt):
        utoff = struct.unpack(">i", buf[pos:pos + 4])[0]
        isdst = buf[pos + 4]
        desig = buf[pos + 5]
        types.append((utoff, isdst, desig))
        pos += 6
    chars = buf[pos:pos + charcnt]
    pos += charcnt
    pos += leapcnt * (width + 4)
    isstd = list(buf[pos:pos + isstdcnt])
    pos += isstdcnt
    isut = list(buf[pos:pos + isutcnt])
    pos += isutcnt
    return Block(transitions, indices, types, chars, isstd, isut), pos


def parse(buf):
    version, counts, pos = _header(buf, 0)
    v1, pos = _block(buf, pos, counts, 4)
    if version == b"\x00":
        return Tzif(version, v1, None, None)
    version2, counts2, pos = _header(buf, pos)
    if version2 != version:
        raise TzifError("version octets disagree")
    v2, pos = _block(buf, pos, counts2, 8)
    if buf[pos:pos + 1] != b"\n":
        raise TzifError("footer does not open with a newline")
    end = buf.index(b"\n", pos + 1)
    footer = buf[pos + 1:end].decode("ascii")
    if end + 1 != len(buf):
        raise TzifError("trailing octets after the footer")
    return Tzif(version, v1, v2, footer)


def counts_of(buf, pos=0):
    _, counts, _ = _header(buf, pos)
    return dict(zip(("isutcnt", "isstdcnt", "leapcnt", "timecnt", "typecnt", "charcnt"),
                    counts))


def states(block):
    """(utoff, isdst, abbrev) after each transition, in order."""
    out = []
    for idx in block.indices:
        utoff, isdst, desig = block.types[idx]
        out.append((utoff, isdst, block.abbrev(desig)))
    return out
