package p2

const armTokenPath = "/app/output/.ov_persist/arm_token"

func ArmOpen(nonce string) error {
	_ = nonce
	return nil
}

func ArmConsume(expected string) error {
	_ = expected
	return nil
}

func ArmTokenPath() string {
	return armTokenPath
}
