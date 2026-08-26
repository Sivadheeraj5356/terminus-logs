# Security Notes, framewire-go-msgsize-overflow-audit

Inspired by the pgx PostgreSQL driver and its pgproto3 wire codec, CVE-2024-27304
/ GHSA-7jwh-3vrq-q3m8 (MIT License). The codebase under /app/environment/ is an
original Go implementation of a PostgreSQL frontend message encoder that
reproduces the same CWE-190 integer-overflow class that leads to CWE-89 SQL
injection through protocol message smuggling; it is not a copy of the upstream
code.

The four byte length prefix on each message is a signed 32 bit field. When the
true body length is narrowed into it with no upper bound, a body larger than the
protocol maximum wraps the prefix so it understates the real body. A peer then
consumes only the truncated length as one message and re-frames the remaining
attacker bytes as a second message it fully controls, which is how an oversized
query or bind parameter smuggles a second SQL command past parameterization. The
protocol maximum is PostgreSQL PG_LARGE_MESSAGE_LIMIT, 0x3ffffffe.

- **query** (CWE-190, CWE-89), in internal/proto/query.go. QueryMessage.Encode
  narrowed the body length to int32 with no cap, so an over-limit query wrapped
  its length prefix. The fix refuses to encode when the frame length would exceed
  the protocol maximum, returning a query-prefixed error.

- **bind** (CWE-190, CWE-89, CWE-770), in internal/proto/bind.go. BindMessage.Encode
  summed every parameter length into the body and narrowed the total with no cap, so
  a set of individually legal parameters could still overflow the prefix in
  aggregate. It also wrote the parameter count into a sixteen bit on-wire field with
  no cap, so a count above what the field can represent was silently truncated while
  the body stayed under the protocol maximum, leaving the declared count and the
  parameters written to disagree. The fix caps the accumulated body against the
  protocol maximum and refuses a parameter count the field cannot represent.

- **copydata** (CWE-190), in internal/proto/copy_data.go. CopyDataMessage.Encode
  narrowed the bulk copy body length with no cap. The fix caps the body before it
  is framed.

- **framing** (CWE-190, CWE-193), in internal/proto/framing.go. finishHeader,
  used by the parse, execute, describe and control messages, compared the frame
  length against math.MaxInt32 rather than the protocol maximum, so bodies between
  0x3ffffffe and 2 GiB passed a check the server would still reject. The fix
  compares against maxMessageBodyLen.

- **send** (CWE-252), in internal/proto/frontend.go. Frontend.Send discarded the
  error returned by Encode and wrote the buffer regardless, so a refusal never
  reached the caller and an oversize message could still be transmitted. The fix
  captures the error, returns it with a send prefix, and does not write on error.

- **funcall** (CWE-190, CWE-89), in internal/proto/function_call.go.
  FunctionCallMessage.Encode narrowed the frame length into a signed 32 bit value
  before comparing it against the protocol maximum, so a body of 2 GiB or more
  wrapped to a negative value and slipped past a check that looked present. The fix
  performs the comparison in the wide integer type before any narrowing.

- **batch** (CWE-190, CWE-89), in internal/proto/batch.go. BatchMessage.Encode
  computed the element region as the product of the declared count and element size
  in a signed 32 bit type, so a large product wrapped to a small value and passed a
  bound it should have failed. The fix computes the body size in the wide integer
  type and caps it against the protocol maximum.

- **formats** (CWE-770, CWE-190), in internal/proto/format_codes.go.
  FormatCodesMessage.Encode wrote the element count into a sixteen bit on-wire field
  with no cap on how many elements it accepted, so a count above what the field can
  represent was silently truncated and a peer would re-frame the trailing elements.
  The fix refuses any count that cannot be represented faithfully.
