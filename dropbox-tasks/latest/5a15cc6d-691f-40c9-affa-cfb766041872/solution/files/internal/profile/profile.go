package profile

import (
	"encoding/binary"
	"fmt"
	"os"
)

// Reason codes stored in the site profile order field.
const (
	CodeUnknownKid byte = 1
	CodeTime       byte = 2
	CodeMissingHdr byte = 3
	CodeBadDigest  byte = 4
	CodeBadMAC     byte = 5
	CodeReplay     byte = 6
)

// OWS mask bits.
const (
	OWSSp   byte = 1 << 0
	OWSHtab byte = 1 << 1
	OWSNbsp byte = 1 << 2
)

// Digest framing modes.
const (
	DigestColonStd byte = 0
	DigestBareStd  byte = 1
	DigestColonURL byte = 2
)

const profileSize = 17

type Profile struct {
	Raw        []byte
	Order      [6]byte
	OWSMask    byte
	DigestMode byte
}

func Load(path string) (Profile, error) {
	var p Profile
	info, err := os.Stat(path)
	if err != nil {
		return p, fmt.Errorf("io")
	}
	if info.IsDir() {
		return p, fmt.Errorf("io")
	}
	data, err := os.ReadFile(path)
	if err != nil {
		return p, fmt.Errorf("io")
	}
	if len(data) != profileSize || string(data[0:4]) != "HRMP" {
		return p, fmt.Errorf("profile_invalid")
	}
	ver := binary.LittleEndian.Uint16(data[4:6])
	flags := binary.LittleEndian.Uint16(data[6:8])
	if ver != 1 || flags != 0 || data[8] != 6 {
		return p, fmt.Errorf("profile_invalid")
	}
	copy(p.Order[:], data[9:15])
	seen := [7]bool{}
	for _, c := range p.Order {
		if c < 1 || c > 6 || seen[c] {
			return p, fmt.Errorf("profile_invalid")
		}
		seen[c] = true
	}
	p.OWSMask = data[15]
	p.DigestMode = data[16]
	if p.OWSMask&^(OWSSp|OWSHtab|OWSNbsp) != 0 {
		return p, fmt.Errorf("profile_invalid")
	}
	if p.DigestMode > DigestColonURL {
		return p, fmt.Errorf("profile_invalid")
	}
	p.Raw = append([]byte(nil), data...)
	return p, nil
}
