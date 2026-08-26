package canon

import (
	"encoding/binary"

	"chainaudit/internal/model"
	"chainaudit/internal/version"
)

// Event encodes ev into its canonical byte representation for the given
// stream. All fixed-width integers are big-endian. The v1 layout has no
// legal_hold byte at all -- not a zero byte, an absent one -- so mixing v1
// and v2 events inside a single checkpoint batch changes the byte width of
// individual records, not just their content.
func Event(stream *model.Stream, ev *model.Event) []byte {
	ver := version.Encoding(stream.MigratedAt, ev.Ts)

	buf := make([]byte, 0, 64+len(ev.Payload))
	buf = append(buf, ver)
	buf = appendLP16(buf, []byte(stream.StreamID))
	buf = appendBE64(buf, uint64(ev.Seq))
	buf = appendBE64(buf, uint64(ev.Ts))
	buf = appendLP16(buf, []byte(ev.EventType))

	if ev.Tombstone {
		buf = append(buf, PayloadTombstone)
		buf = appendLP32(buf, TombstoneSentinel[:])
	} else {
		buf = append(buf, PayloadNormal)
		buf = appendLP32(buf, ev.Payload)
	}

	if ver == version.V2 {
		if ev.LegalHold {
			buf = append(buf, 0x01)
		} else {
			buf = append(buf, 0x00)
		}
	}

	return buf
}

func appendLP16(buf, data []byte) []byte {
	var lenBuf [2]byte
	binary.BigEndian.PutUint16(lenBuf[:], uint16(len(data)))
	buf = append(buf, lenBuf[:]...)
	return append(buf, data...)
}

func appendLP32(buf, data []byte) []byte {
	var lenBuf [4]byte
	binary.BigEndian.PutUint32(lenBuf[:], uint32(len(data)))
	buf = append(buf, lenBuf[:]...)
	return append(buf, data...)
}

func appendBE64(buf []byte, v uint64) []byte {
	var b [8]byte
	binary.BigEndian.PutUint64(b[:], v)
	return append(buf, b[:]...)
}
