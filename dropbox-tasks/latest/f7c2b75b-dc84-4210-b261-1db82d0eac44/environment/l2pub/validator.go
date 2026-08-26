package l2pub

import "fmt"

func ValidatePublishFrame(payload string, mtu int) error {
	if err := ValidateFrameMTU(payload, mtu); err != nil {
		return err
	}
	if FrameChecksum(payload) == "" {
		return fmt.Errorf("checksum failed")
	}
	return nil
}
