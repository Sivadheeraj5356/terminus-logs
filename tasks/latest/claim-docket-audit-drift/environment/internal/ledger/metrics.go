package ledger

import "example.com/claimdocketaudit/internal/frame"

func SeqSpan(frames []frame.Frame) (minSeq, maxSeq uint64) {
	if len(frames) == 0 {
		return 0, 0
	}
	minSeq = frames[0].Seq
	maxSeq = frames[0].Seq
	for _, fr := range frames[1:] {
		if fr.Seq < minSeq {
			minSeq = fr.Seq
		}
		if fr.Seq > maxSeq {
			maxSeq = fr.Seq
		}
	}
	return minSeq, maxSeq
}

func TransferAmountSum(frames []frame.Frame) int64 {
	var sum int64
	for _, fr := range frames {
		p := fr.Payload
		if (p.Kind == "upsert" || p.Kind == "transfer") && p.HasAmount {
			sum += p.Amount
		}
	}
	return sum
}
