# framewire wire framing contract

This document is the authoritative contract for how framewire encodes PostgreSQL
frontend messages. It describes the behaviour the encoders must satisfy. It does
not describe where any current encoder falls short.

## Message framing

A frontend message on the wire is a one byte type tag, then a four byte
big-endian length, then the body. The length field counts itself plus the body
but not the type tag, so its value is `4 + len(body)`. The length field is a
signed 32 bit integer. The startup message is the one exception: it has no type
tag and begins directly with its length.

Some messages carry a count of repeated elements ahead of the elements
themselves. A count is written into a fixed width on-wire field, so the number of
elements a message can carry is bounded by what that field can represent as well
as by the overall body length.

## The protocol maximum

A single message may not exceed the PostgreSQL protocol maximum of `0x3ffffffe`
bytes (this mirrors `PG_LARGE_MESSAGE_LIMIT`, which is `MaxAllocSize - 1`).

Every length or count that an encoder derives from a message must be validated
against the limit that applies to it, the protocol maximum for a body length and
the width of its on-wire field for a count, before it is used to size, index, or
advance a buffer. The arithmetic that performs that validation must be carried out
in a type wide enough that it cannot itself overflow, narrow, or wrap, because a
check computed in a signed 32 bit value can pass for a body that is in fact far
larger than the value being tested. An encoder must never emit a frame whose
length prefix disagrees with the body it actually wrote: if the real frame length
cannot be represented faithfully in the signed 32 bit length field it must refuse
to produce the message and return an error rather than write a truncated or
wrapped prefix. This obligation applies to every frontend message the codec can
build and to the frontend send path that hands an encoded message to the wire.

A message whose frame length is exactly the protocol maximum is legal and must
still encode.

## Refusal shape

When an encoder refuses a message it returns an error whose text leads with the
subsystem it came from and names the resource that was exceeded, for example
`exceeds protocol maximum` or `too large`. The subsystem is the message kind that
refused it for a per-message check, `framing` for the shared header helper, or
`send` for the transmit path. A refusal is an ordinary returned error: the encoder
must never panic, and the send path must surface the refusal to its caller instead
of transmitting the message anyway.

## The framewire tool

`framewire frame <spec>` builds one message from a spec file and encodes it
directly, printing `ok kind=<k> declared=<d> intended=<i>` on success, where
`declared` is the length field that was written and `intended` is the true frame
length. `framewire send <spec>` builds one message and hands it to the frontend
send path. Both commands exit non zero and print the refusal on stderr when the
message cannot be framed.

A spec file is a set of `key=value` lines. The keys are `kind` (one of query,
bind, copydata, parse, execute, funcall, batch, formats), `content`, `stmt`,
`portal`, `fill`, `params`, `count`, and `elemsize`. `fill` is a declared body
length, `params` is a comma separated list of declared parameter lengths for a
bind, `count` is a declared element count, and `elemsize` is a declared per
element size. These declared lengths let a spec describe a body far larger than
the bytes it carries on disk, so the length arithmetic of an encoder is exercised
without materializing the whole body.
