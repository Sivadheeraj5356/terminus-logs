package fusion

// Outcome is the result of running verbs for one read.
type Outcome struct {
	Logged bool
	Check  string
}

// Blend runs the verb list against manifest fields for path p.
func Blend(verbs []int, digest, hmac, sig string) Outcome {
	var o Outcome
	o.Check = "skip"
	for _, v := range verbs {
		switch v {
		case 1:
			o.Logged = true
		case 2:
			if sig == "ffffffffffffffff" {
				o.Check = "fail"
			} else {
				o.Check = "pass"
			}
		case 4:
			if hmac == "ffffffffffffffff" {
				o.Check = "fail"
			} else if o.Check != "fail" {
				o.Check = "pass"
			}
		}
	}
	_ = digest
	return o
}

// Verdict folds logged and check into ok/bad.
func Verdict(o Outcome, wantLog bool, wantCheck bool) string {
	if wantLog && !o.Logged {
		return "bad"
	}
	if wantCheck {
		if o.Check == "fail" {
			return "bad"
		}
		if o.Check != "pass" {
			return "bad"
		}
	}
	if !wantLog && o.Logged {
		return "bad"
	}
	return "ok"
}
