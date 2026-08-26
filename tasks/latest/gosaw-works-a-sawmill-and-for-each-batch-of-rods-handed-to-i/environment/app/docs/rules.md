gosaw works a sawmill. It is handed a batch of rods, each a whole number of units of timber
long, and for the batch it reports whether the player who is about to saw can force a win,
and when they can, one cut that does it. Each batch is judged on its own; the batches of a
session do not bear on one another. The verdict for a batch never changes from one run to the
next, and when more than one cut wins a batch any one of them may be the one named.

The game. A batch is a row of rods. On a turn the player to saw makes exactly one cut. A cut
picks a single rod and saws it across into two rods whose lengths are whole numbers, each one
or more. The two players take turns, and the player who makes the last cut wins. A player who
faces a row with no cut left to make cannot move at all, and that player has lost, because the
other player made the last cut on the turn before. The empty row, with nothing to saw, is a
loss for the player to saw. There is always a definite answer.

The gaps. A rod of nought units is an empty place in the row, a gap. A gap has no timber and
can never be sawn, but it holds its spot in the order all the same and is counted in the
numbering of the rods. The gaps also set the blade, and this is the whole of it: count the
gaps in the row, the rods of nought units. When that count is even, or there are no gaps at
all, the blade runs heavy and eats one unit of timber at every cut. When that count is odd,
the blade runs true and eats nothing. The setting holds for the whole batch, the same for both
players, and no cut ever adds or removes a gap, so it never shifts once the row is read.

The heavy blade. With the blade heavy, an even number of gaps or none, a cut loses one unit to
the blade as sawdust, which falls away and leaves the table. So where one rod of length n stood
there now stand two rods, each one or more, whose lengths add to n minus one. A rod must be
long enough to give up that unit and still leave a rod of at least one unit on each side of the
cut, so only a rod of three units or more can be sawn; a rod of one or two units is finished
and stays as it is, for after the blade took its unit there would be nothing, or only a single
unit, left to fall into two rods.

The true blade. With the blade true, an odd number of gaps, a cut loses nothing. So where one
rod of length n stood there now stand two rods, each one or more, whose lengths add to n. A rod
of two units can now be sawn, into a rod of one and a rod of one; only a rod of one unit is
finished, since a single unit cannot fall into two rods of at least one each.

Who wins, worked out. Give every rod a worth, a whole number that is nought or more, and give
the whole batch the worth that is the bitwise exclusive-or of the worths of its rods. The batch
is a loss for the player to saw exactly when this combined worth is nought, and a win when it
is anything else. The worth of a rod is the smallest whole number, counting from nought, that
is not the worth of any batch that rod can be turned into by a single cut, where the cuts are
exactly the ones above for the blade this row is set to. A rod that cannot be sawn under the
blade in force can be turned into no batch at all, so its worth is nought.

So a rod's worth is not fixed to the rod. It is worked up from the worths of the shorter rods,
cut by cut, under whichever blade the gaps in the row have set, and the same length of rod is
in general worth one thing on a heavy blade and another on a true one. A rod is not worth the
units of timber standing in it, and the one unit the heavy blade eats works its way up through
the worths with no closed form. Read the worth of every rod under the blade this row is set to,
by the count of its gaps, before combining them.

The cut. When the player to saw loses, the output says so and names no cut. When the player to
saw wins, the output names one cut that leaves the opponent a batch of nought worth. Any legal
cut that reaches such a batch is accepted, and from a winning batch such a cut always exists. A
cut must pick a rod long enough to saw under the blade in force and saw it into two rods that
each hold at least one unit and whose lengths add to n or to n minus one as the blade sets,
leaving the other rods, and the gaps, untouched.

Writing the cut. A cut is written

    cut rod I into A and B

where I is the rod number and A and B are the lengths of the two rods it becomes, in any
order, each one or more, adding to the length of rod I on a true blade or to one less on a
heavy blade.

Invocation and input and output. The path to the mill file is the single command-line
argument. If the program is run with anything other than exactly one argument, or the file
cannot be read, it writes nothing and exits with status 2. Otherwise batches arrive on
standard input, one per line, and the program exits 0. A batch line is split on whitespace
into fields. A field is a whole-number literal when it is an optional single leading plus or
minus sign followed by one or more decimal digits, and nothing else, and the number it spells
fits a signed 64-bit integer. A run of digits too large to fit one is not a whole-number
literal. A line with no fields, or any field that is not a whole-number literal, is skipped
and produces no output. Every other line produces exactly one output line, in input order.

Reading a batch. Each field of a batch line is the length of one rod, in the order written,
and is read as the whole number the literal spells. A negative field like -1 is a whole number
all the same: it is read as that number and then judged out of range, never treated as a
non-number and never skipped on that account. A rod is in range when its length is nought or
more and, when the mill file sets a bound, no greater than that bound. When every field is a
whole-number literal but at least one rod is out of range, whether below nought or above the
bound, the batch is not a legal setup for this mill: the output echoes it and reports the word
ILLEGAL, with no verdict and no cut. The rods are numbered from one, left to right, and the
gaps are counted in that numbering. The batch is echoed at the front of its output line as the
rod lengths in that order, each read from its literal and written back in plain decimal and
joined by single spaces, so a field written 007 echoes as 7 and a field written +3 echoes as 3.

The mill file. The mill file is read one line at a time. Everything from the first # on a line
to the end of the line is a comment and is dropped, and the surrounding whitespace is then
trimmed. A line that begins with longest: sets the greatest length a single rod may have at
this bench, read from the first word after longest: when that word is a run of decimal digits
naming a whole number nought or more that fits a signed 64-bit integer; a word that is not
such a run, whether it carries a sign or is too large to fit, leaves the setting where it
stood. When the bound is set more than once the last line that sets a value stands, and when it
is never set there is no bound and every rod of nought or more units is in range. All other
lines of the mill file are ignored.

Output and exit codes. Each batch that produces output prints a single line

    RODS | VERDICT

where RODS is the rod lengths in order, each in decimal, joined by single spaces, and VERDICT
is one of three things. It is the word ILLEGAL when a rod is out of range for this mill.
Otherwise it is the word LOSS when the player to saw cannot force a win, standing alone with no
cut after it, including on the empty row where no rod can be sawn. Otherwise it is the word WIN
when the player to saw can force a win, followed by a single space and the chosen cut. The
program exits 0 once every input line has been read.
