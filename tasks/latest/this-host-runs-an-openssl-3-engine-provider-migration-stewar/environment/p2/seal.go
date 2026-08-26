package p2

import (
	"os"

	"local/ovws/lib"
)

const (
	persistDir = "/app/output/.ov_persist"
	bindPath   = persistDir + "/bind_stamp.json"
	genPath    = "/app/environment/var/mig/suite_gen"
	stampPath  = "/app/environment/var/mig/seal_stamp.json"
)

func EpochExpect() int {
	return lib.SlotSum()
}

func SuiteCycle() int {
	return readGen()
}

func readGen() int {
	b, err := os.ReadFile(genPath)
	if err != nil {
		return 0
	}
	n := 0
	for _, c := range b {
		if c >= '0' && c <= '9' {
			n = n*10 + int(c-'0')
		}
	}
	return n
}

func SealPrepare() error {
	return nil
}

func SealFinalize() error {
	jnl, err := os.ReadFile(JnlPath())
	if err == nil && len(jnl) > 0 {
		_ = os.WriteFile(ResPath(), jnl, 0o644)
	}
	_ = LatchSet("sealed")
	gen := readGen()
	return os.WriteFile(genPath, []byte(itoa(gen+1)+"\n"), 0o644)
}

func itoa(n int) string {
	if n == 0 {
		return "0"
	}
	var buf [16]byte
	i := len(buf)
	for n > 0 {
		i--
		buf[i] = byte('0' + n%10)
		n /= 10
	}
	return string(buf[i:])
}

func BindStampPath() string {
	return bindPath
}

func StampPath() string {
	return stampPath
}
