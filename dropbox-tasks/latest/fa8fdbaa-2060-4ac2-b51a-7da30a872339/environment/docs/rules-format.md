# Chronicle rules format

Each world's chronicle is a markdown file mixing narrative lore paragraphs
with machine-readable forbidden-rule lines. A chronicle may contain any
number of these lines, anywhere in the file, each on its own line with no
surrounding markdown syntax:

@RULE forbidden room=ROOM_ID verb=VERB target=TARGET

ROOM_ID, VERB, and TARGET are plain tokens with no internal whitespace.
For a move candidate, VERB is the exit's verb and TARGET is the exit's to
room id. For an action candidate, VERB and TARGET are the action's own
verb and target. For a take candidate, VERB is always take and TARGET is
the item's id.

A chronicle's complete forbidden set is every @RULE forbidden line it
contains, parsed in file order; there is no limit of one rule per
chronicle. A room/verb/target trio is forbidden if it exactly matches any
one of those parsed lines. The assemble stage (see
/app/docs/probe-assemble-pipeline.md) removes a candidate from the assembled
hints whenever its room, verb, and target match a forbidden rule from the
chronicle its session's world_id currently resolves to, and the attempt
endpoint (see /app/docs/oracle-contract.md) refuses an attempt on the same
basis.
