package eng

import (
	"fmt"

	"qxhub/gst"
	"qxhub/led"
	"qxhub/zeb"
)

// rgy_knit rebuilds the durable session registry and the current generation
// pointer from the committed ledger after a registry loss.
func rgy_knit() error {
	ents, err := led.ReplayAll()
	if err != nil {
		return err
	}
	if len(ents) == 0 {
		return fmt.Errorf("no ledger to replay")
	}
	last := ents[len(ents)-1]
	var sess zeb.Session
	sess.ActiveGen = last.Gen
	sess.Floor = last.Gen
	sess.LastArm = last.Arm
	if err := zeb.Save(sess); err != nil {
		return err
	}
	return gst.SetCurrent(last.Gen)
}

// ReplayRegistry is the public wrapper around rgy_knit.
func ReplayRegistry() error {
	return rgy_knit()
}
