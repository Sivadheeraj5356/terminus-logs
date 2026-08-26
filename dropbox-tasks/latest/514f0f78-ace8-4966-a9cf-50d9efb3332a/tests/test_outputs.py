"""This module contains exactly 36 tests."""
from __future__ import annotations

import math

from ctc_utterance_foundry import (
    CaptionSession,
    OP_DECODE,
    OP_FINISH,
    OP_RESET,
    TOKENS,
    assert_error,
    assert_finite_hypotheses,
    assert_ok,
    best,
    finish,
    frame,
    ids,
    permute_case,
    shifted,
    texts,
    tied,
)


def test_ctcforge_mailbox_accepts_one_complete_utterance():
    """A complete mailbox utterance returns a successful n-best CTC verdict."""
    reply = finish([frame(1), frame(0), frame(2)])
    assert_ok(reply)
    assert best(reply)["text"] == "ab"


def test_ctcforge_malformed_offsets_reject_without_process_exit():
    """Malformed mailbox lengths reject without ending the persistent decoder process."""
    with CaptionSession() as session:
        bad = session.request(logits=[frame(1)], token_bytes_delta=99).obj
        good = session.request(request_id=2, stream=2, logits=[frame(1)]).obj
    assert_error(bad, "CTC_MALFORMED")
    assert_ok(good)
    assert best(good)["text"] == "a"


def test_ctcforge_nonfinite_logit_is_rejected():
    """A non-finite logit is rejected as invalid model evidence."""
    row = frame(1)
    row[2] = math.nan
    reply = finish([row])
    assert_error(reply, "CTC_NONFINITE")


def test_ctcforge_blank_only_frames_decode_to_empty_transcript():
    """All-blank evidence decodes to the empty transcript without spans."""
    reply = finish([frame(0), frame(0), frame(0)])
    assert_ok(reply)
    assert best(reply)["text"] == ""
    assert best(reply)["spans"] == []


def test_ctcforge_single_label_collapses_across_adjacent_frames():
    """Adjacent identical labels without a blank collapse to one token."""
    reply = finish([frame(1), frame(1), frame(1)])
    assert_ok(reply)
    assert ids(reply) == [1]


def test_ctcforge_repeated_label_requires_intervening_blank():
    """The same label separated by blank may produce a repeated output token."""
    reply = finish([frame(1), frame(0), frame(1)])
    assert_ok(reply)
    assert ids(reply) == [1, 1]


def test_ctcforge_prefix_merge_sums_blank_and_nonblank_paths():
    """Blank and nonblank path masses merge into one unique prefix."""
    reply = finish([tied(0, 1), tied(0, 1)], topn=4)
    assert_ok(reply)
    assert texts(reply).count("a") == 1
    assert best(reply)["text"] in {"", "a"}


def test_ctcforge_logit_shift_per_frame_preserves_hypotheses():
    """Adding a constant to every logit in a frame preserves hypotheses."""
    logits = [frame(1), tied(0, 2), frame(2)]
    a = finish(logits, topn=3)
    b = finish(shifted(logits, 17.0), topn=3)
    assert_ok(a)
    assert_ok(b)
    assert texts(a) == texts(b)
    for ha, hb in zip(a["hypotheses"], b["hypotheses"]):
        assert abs(ha["acoustic"] - hb["acoustic"]) < 1e-6
        assert abs(ha["total"] - hb["total"]) < 1e-6
        assert ha["spans"] == hb["spans"]
        assert abs(ha["confidence"] - hb["confidence"]) < 1e-6


def test_ctcforge_extreme_logits_remain_numerically_finite():
    """Extreme finite logits still produce finite scores and confidence."""
    reply = finish([frame(1, high=1000, low=-1000), frame(0, high=1000, low=-1000), frame(2, high=1000, low=-1000)])
    assert_ok(reply)
    assert_finite_hypotheses(reply)


def test_ctcforge_beam_pruning_uses_merged_prefix_score():
    """Beam pruning keeps prefixes after equivalent path masses are merged."""
    reply = finish([tied(0, 1), tied(0, 1), frame(2)], beam=2, topn=2, prune=-20)
    assert_ok(reply)
    assert "ab" in texts(reply) or "b" in texts(reply)


def test_ctcforge_top_paths_are_unique_collapsed_sequences():
    """N-best results contain unique collapsed token sequences."""
    reply = finish([tied(0, 1, 2), tied(0, 1, 2)], topn=6, beam=6)
    assert_ok(reply)
    seqs = [tuple(h["ids"]) for h in reply["hypotheses"]]
    assert len(seqs) == len(set(seqs))


def test_ctcforge_tied_hypotheses_use_canonical_token_order():
    """Tied hypotheses are ordered by canonical token id sequence."""
    reply = finish([tied(1, 2)], topn=3, beam=4)
    assert_ok(reply)
    nonempty = [h for h in reply["hypotheses"] if h["ids"]]
    assert nonempty[0]["ids"] == [1]


def test_ctcforge_vocabulary_permutation_preserves_text():
    """Consistent vocabulary and logit permutation preserves transcript text."""
    logits = [frame(1), frame(0), frame(2)]
    perm = [0, 2, 1, 3, 4, 5]
    plogits, ptokens, _inv = permute_case(logits, TOKENS, perm)
    a = finish(logits)
    b = finish(plogits, tokens=ptokens)
    assert_ok(a)
    assert_ok(b)
    assert best(a)["text"] == best(b)["text"] == "ab"


def test_ctcforge_chunk_split_matches_batch_transcript():
    """A legal chunk split has the same finished transcript as batch decoding."""
    logits = [frame(1), frame(0), frame(2), frame(3)]
    batch = finish(logits, stream=10)
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=11, logits=logits[:2])
        streamed = session.request(op=OP_FINISH, stream=11, logits=logits[2:]).obj
    assert_ok(batch)
    assert_ok(streamed)
    assert best(batch)["text"] == best(streamed)["text"]


def test_ctcforge_chunk_split_matches_batch_scores():
    """A legal chunk split has the same finished ordered scores as batch decoding."""
    logits = [frame(1), tied(0, 2), frame(2)]
    batch = finish(logits, stream=12, topn=2)
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=13, logits=logits[:1], topn=2)
        streamed = session.request(op=OP_FINISH, stream=13, logits=logits[1:], topn=2).obj
    assert abs(best(batch)["total"] - best(streamed)["total"]) < 1e-5


def test_ctcforge_chunk_boundary_preserves_repeated_token_rule():
    """A chunk boundary does not replace the blank required between repeats."""
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=14, logits=[frame(1)])
        session.request(op=OP_DECODE, stream=14, logits=[frame(0)])
        reply = session.request(op=OP_FINISH, stream=14, logits=[frame(1)]).obj
    assert_ok(reply)
    assert ids(reply) == [1, 1]


def test_ctcforge_empty_middle_chunk_preserves_stream_state():
    """An empty middle chunk preserves accumulated stream state."""
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=15, logits=[frame(1)])
        session.request(op=OP_DECODE, stream=15, logits=[])
        reply = session.request(op=OP_FINISH, stream=15, logits=[frame(2)]).obj
    assert_ok(reply)
    assert best(reply)["text"] == "ab"


def test_ctcforge_final_chunk_flushes_pending_word():
    """Finish applies phrase completion to the pending final transcript."""
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=16, logits=[frame(1)], biases=[("a", 2.0)])
        reply = session.request(op=OP_FINISH, stream=16, logits=[], biases=[("a", 2.0)]).obj
    assert_ok(reply)
    assert best(reply)["bias"] == 2


def test_ctcforge_reset_discards_only_named_stream():
    """Reset clears only the named stream and leaves another stream intact."""
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=17, logits=[frame(1)])
        session.request(op=OP_DECODE, stream=18, logits=[frame(2)])
        session.request(op=OP_RESET, stream=17)
        cleared = session.request(op=OP_FINISH, stream=17, logits=[]).obj
        kept = session.request(op=OP_FINISH, stream=18, logits=[]).obj
    assert_ok(cleared)
    assert_ok(kept)
    assert best(cleared)["text"] == ""
    assert best(cleared)["spans"] == []
    assert best(kept)["text"] == "b"


def test_ctcforge_interleaved_streams_remain_independent():
    """Interleaved stream ids maintain independent accumulated logits."""
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=19, logits=[frame(1)])
        session.request(op=OP_DECODE, stream=20, logits=[frame(2)])
        a = session.request(op=OP_FINISH, stream=19, logits=[frame(3)]).obj
        b = session.request(op=OP_FINISH, stream=20, logits=[frame(3)]).obj
    assert best(a)["text"] == "ac"
    assert best(b)["text"] == "bc"


def test_ctcforge_word_bias_applies_once_at_completion():
    """A completed phrase receives its completion bias exactly once."""
    reply = finish([frame(1), frame(2)], biases=[("ab", 3.5)])
    assert_ok(reply)
    assert best(reply)["text"] == "ab"
    assert best(reply)["bias"] == 3.5


def test_ctcforge_partial_hotword_receives_no_full_bonus():
    """A partial phrase prefix receives no full completion bonus."""
    reply = finish([frame(1)], biases=[("ab", 4.0)])
    assert_ok(reply)
    assert best(reply)["text"] == "a"
    assert best(reply)["bias"] == 0


def test_ctcforge_completed_hotword_changes_candidate_order():
    """A completed hotword can change the ordered candidate list after pruning."""
    logits = [tied(1, 2), tied(2, 3)]
    plain = finish(logits, beam=8, topn=4)
    biased = finish(logits, beam=8, topn=4, biases=[("ab", 5.0)])
    assert_ok(plain)
    assert_ok(biased)
    assert best(biased)["text"] == "ab"


def test_ctcforge_overlapping_hotwords_keep_distinct_progress():
    """Overlapping completed phrases each contribute their independent bias."""
    reply = finish([frame(1), frame(2), frame(3)], biases=[("ab", 2.0), ("abc", 3.0)])
    assert_ok(reply)
    assert best(reply)["text"] == "abc"
    assert best(reply)["bias"] == 5.0


def test_ctcforge_bias_cannot_revive_pruned_impossible_prefix():
    """Phrase bias does not revive a prefix removed by acoustic beam pruning."""
    logits = [frame(1), frame(2)]
    reply = finish(logits, beam=1, topn=1, biases=[("c", 50.0)])
    assert_ok(reply)
    assert best(reply)["text"] == "ab"


def test_ctcforge_alignment_span_covers_selected_token_frames():
    """Token spans cover the selected frames for the collapsed sequence."""
    reply = finish([frame(1), frame(0), frame(2)])
    assert_ok(reply)
    assert best(reply)["spans"] == [[0, 1], [2, 3]]


def test_ctcforge_alignment_handles_repeated_tokens():
    """Repeated output tokens separated by blank have distinct spans."""
    reply = finish([frame(1), frame(0), frame(1)])
    assert_ok(reply)
    assert best(reply)["spans"] == [[0, 1], [2, 3]]


def test_ctcforge_empty_transcript_has_no_spans():
    """The empty transcript has no token-frame spans."""
    reply = finish([frame(0), frame(0)])
    assert_ok(reply)
    assert best(reply)["ids"] == []
    assert best(reply)["spans"] == []


def test_ctcforge_confidence_stays_in_closed_unit_interval():
    """Every reported n-best confidence lies in the closed unit interval."""
    reply = finish([tied(0, 1, 2), tied(0, 1, 2)], topn=5, beam=6)
    assert_ok(reply)
    for hyp in reply["hypotheses"]:
        assert 0 <= hyp["confidence"] <= 1


def test_ctcforge_confidence_uses_normalized_nbest_mass():
    """N-best confidence is normalized over total (not acoustic) n-best mass."""
    reply = finish([tied(1, 2), tied(2, 3)], topn=4, beam=8, biases=[("ab", 2.0)])
    assert_ok(reply)
    hyps = reply["hypotheses"]
    assert abs(sum(h["confidence"] for h in hyps) - 1.0) < 2e-6
    assert any(abs(h["acoustic"] - h["total"]) > 1e-9 for h in hyps)
    peak = max(h["total"] for h in hyps)
    mass = [math.exp(h["total"] - peak) for h in hyps]
    denom = sum(mass)
    for hyp, weight in zip(hyps, mass):
        assert abs(hyp["confidence"] - weight / denom) < 1e-5


def test_ctcforge_larger_beam_does_not_lose_previous_best():
    """Increasing beam width does not remove the former best hypothesis."""
    logits = [tied(0, 1, 2), frame(2), frame(3)]
    small = finish(logits, beam=2, topn=2)
    large = finish(logits, beam=8, topn=6)
    assert best(small)["text"] in texts(large)


def test_ctcforge_top_path_count_respects_available_unique_paths():
    """The reply never reports more unique paths than requested top count."""
    reply = finish([tied(0, 1, 2)], topn=2, beam=8)
    assert_ok(reply)
    assert len(reply["hypotheses"]) <= 2


def test_ctcforge_repeated_request_is_byte_identical():
    """Identical fresh-state requests produce identical response bytes."""
    with CaptionSession() as session:
        first = session.request(stream=50, logits=[frame(1), frame(2)]).raw
        second = session.request(stream=50, logits=[frame(1), frame(2)]).raw
    assert first == second


def test_ctcforge_request_order_does_not_change_fresh_stream():
    """A previous unrelated request does not change a later fresh stream."""
    with CaptionSession() as session:
        session.request(stream=60, logits=[frame(3)])
        after = session.request(stream=61, logits=[frame(1), frame(2)]).raw
    with CaptionSession() as session:
        alone = session.request(stream=61, logits=[frame(1), frame(2)]).raw
    assert after == alone


def test_ctcforge_rejection_does_not_poison_next_utterance():
    """A rejected request leaves no stale state for the next utterance."""
    with CaptionSession() as session:
        badrow = frame(1)
        badrow[0] = math.inf
        bad = session.request(stream=70, logits=[badrow]).obj
        good = session.request(stream=70, logits=[frame(2)]).obj
    assert_error(bad, "CTC_NONFINITE")
    assert best(good)["text"] == "b"


def test_ctcforge_batch_and_streamed_verdicts_match_end_to_end():
    """Batch and streamed decoding agree on tokens, scores, spans, and confidence."""
    logits = [frame(1), frame(0), frame(2), frame(3)]
    batch = finish(logits, stream=80, topn=3, biases=[("abc", 1.5)])
    with CaptionSession() as session:
        session.request(op=OP_DECODE, stream=81, logits=logits[:1], topn=3, biases=[("abc", 1.5)])
        session.request(op=OP_DECODE, stream=81, logits=logits[1:3], topn=3, biases=[("abc", 1.5)])
        streamed = session.request(op=OP_FINISH, stream=81, logits=logits[3:], topn=3, biases=[("abc", 1.5)]).obj
    assert best(batch)["ids"] == best(streamed)["ids"]
    assert abs(best(batch)["total"] - best(streamed)["total"]) < 1e-5
    assert best(batch)["spans"] == best(streamed)["spans"]
    assert abs(best(batch)["confidence"] - best(streamed)["confidence"]) < 1e-6
