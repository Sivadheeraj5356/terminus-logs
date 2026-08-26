"""Memfd/eventfd CTC foundry and independent request helpers."""
from __future__ import annotations

import json
import mmap
import os
import struct
import subprocess
from dataclasses import dataclass

MAILBOX_SIZE = 1 << 20
REQUEST_OFFSET = 128
RESPONSE_OFFSET = 1 << 19
OP_DECODE = 1
OP_FINISH = 2
OP_RESET = 3
TOKENS = ["_", "a", "b", "c", " ", "x"]

@dataclass
class Reply:
    raw: bytes
    obj: dict

class CaptionSession:
    def __init__(self) -> None:
        self.memfd = os.memfd_create("ctc-mailbox", flags=0)
        os.ftruncate(self.memfd, MAILBOX_SIZE)
        self.map = mmap.mmap(self.memfd, MAILBOX_SIZE)
        self.reqfd = os.eventfd(0, 0)
        self.respfd = os.eventfd(0, 0)
        for fd in (self.memfd, self.reqfd, self.respfd):
            os.set_inheritable(fd, True)
        env = os.environ.copy()
        env["CAPTION_MAILBOX_FD"] = str(self.memfd)
        env["CAPTION_REQUEST_EVENT_FD"] = str(self.reqfd)
        env["CAPTION_RESPONSE_EVENT_FD"] = str(self.respfd)
        self.proc = subprocess.Popen(["/app/build/caption-beam"], pass_fds=(self.memfd, self.reqfd, self.respfd), env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    def request(self, *, op=OP_FINISH, request_id=1, stream=1, logits=None, tokens=None, blank=0, beam=8, topn=3, prune=-30.0, biases=None, corrupt_header=False, token_bytes_delta=0) -> Reply:
        logits = [] if logits is None else logits
        tokens = TOKENS if tokens is None else tokens
        biases = [] if biases is None else biases
        frames = len(logits)
        vocab = len(tokens)
        flat = [float(x) for row in logits for x in row]
        token_blob = bytearray()
        for tok in tokens:
            data = tok.encode()
            token_blob += struct.pack("<H", len(data)) + data
        bias_blob = bytearray(struct.pack("<I", len(biases)))
        for phrase, weight in biases:
            data = phrase.encode()
            bias_blob += struct.pack("<H", len(data)) + data + struct.pack("<f", float(weight))
        header = bytearray(128)
        header[:4] = b"BAD!" if corrupt_header else b"CTC1"
        struct.pack_into("<IQQIIIIIfII", header, 4, op, request_id, stream, frames, vocab, blank, beam, topn, float(prune), len(token_blob) + token_bytes_delta, len(bias_blob))
        payload = struct.pack("<" + "f" * len(flat), *flat) + token_blob + bias_blob
        self.map.seek(0)
        self.map.write(b"\x00" * MAILBOX_SIZE)
        self.map.seek(0)
        self.map.write(header)
        self.map.seek(REQUEST_OFFSET)
        self.map.write(payload)
        os.write(self.reqfd, struct.pack("<Q", 1))
        os.read(self.respfd, 8)
        self.map.seek(64)
        n = struct.unpack("<I", self.map.read(4))[0]
        self.map.seek(RESPONSE_OFFSET)
        raw = self.map.read(n)
        return Reply(raw=raw, obj=json.loads(raw.decode()))

    def close(self):
        for fd in (self.reqfd, self.respfd, self.memfd):
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            out, err = self.proc.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            self.proc.terminate()
            out, err = self.proc.communicate(timeout=2)
        self.map.close()
        return out, err, self.proc.returncode

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

def frame(best: int, vocab: int = 6, high: float = 5.0, low: float = -5.0):
    row = [low] * vocab
    row[best] = high
    return row

def tied(*ids: int, vocab: int = 6, base: float = -8.0, val: float = 1.0):
    row = [base] * vocab
    for idx in ids:
        row[idx] = val
    return row

def finish(logits, **kw):
    with CaptionSession() as s:
        return s.request(logits=logits, **kw).obj

def texts(reply):
    return [h["text"] for h in reply["hypotheses"]]

def ids(reply, rank=0):
    return reply["hypotheses"][rank]["ids"]

def best(reply):
    return reply["hypotheses"][0]

def assert_ok(reply):
    assert reply["ok"] is True
    assert "hypotheses" in reply

def assert_error(reply, code):
    assert reply["ok"] is False
    assert reply["code"] == code

def assert_finite_hypotheses(reply):
    for hyp in reply["hypotheses"]:
        for name in ("acoustic", "bias", "total", "confidence"):
            assert hyp[name] == hyp[name]
            assert abs(hyp[name]) < 1e100

def shifted(logits, shift):
    return [[x + shift for x in row] for row in logits]

def permute_case(logits, tokens, perm):
    inv = {old: new for new, old in enumerate(perm)}
    new_tokens = [tokens[i] for i in perm]
    new_logits = [[row[i] for i in perm] for row in logits]
    return new_logits, new_tokens, inv
