package eng

import "qxhub/zeb"

func runGen(sess *zeb.Session, phase, arm string) {
	zeb.Advance(sess, phase, arm)
}
