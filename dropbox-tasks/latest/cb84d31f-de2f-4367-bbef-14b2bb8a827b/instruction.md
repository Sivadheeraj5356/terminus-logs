gosaw works a sawmill and, for each batch of rods handed to it, says who is winning. A rod is a
whole number of units of timber long. A turn is one cut: a player takes a single rod and saws it
across into two rods, each one unit or more. The two players take turns, and the player who
makes the last cut wins, so the player faced with a row too short to saw has lost.

How much a cut costs depends on the row. A rod of nought units is an empty place, a gap, that
holds its spot but can never be sawn. The gaps set the blade for the whole batch. When the row
holds an even number of gaps, or none, the blade runs heavy and eats one unit of timber at each
cut, so the two rods left add to one less than the rod that was sawn and only a rod of three or
more can be sawn. When the row holds an odd number of gaps the blade runs true and eats nothing,
so the two rods add to the whole rod and a rod of two saws into two ones. The setting holds for
both players and no cut ever changes it.

The mill file, the tool's only argument, can set the longest rod this bench will take. Batches
come in on standard input, one to a line, as rod lengths separated by spaces. For each one gosaw
echoes the row back and says whether the player to saw can force a win, and when they can it
names one cut that does it, on a numbered rod. A rod longer than the bench allows, or a length
below nought, is out of range and the batch is called out rather than sawn. A negative length is
a number all the same and is called out the same way, not skipped. A line that is not a list of
numbers is passed over.

As it stands gosaw clears the easy batches but calls a good many close ones backwards. It scores
every rod at the units of timber sitting in it, as if the timber were a plain heap of tokens, and
it reads the same blade for every row. It forgets that a cut can lose a unit to the blade, which
quietly changes what a rod is worth, and it forgets that the gaps in a row decide the blade at
all, so the same rod is worth one thing in one row and another beside a gap. A sample bench and a
batch of rods sit in /app/fixtures, and the full rules, how a batch is judged won or lost, how a
rod is weighed and how the gaps set the blade, are in /app/docs/rules.md. Settle the close cuts by
playing them out. The reckoning that needs putting right is the java in /app/Sawmill.java, and the
tool is run with the mill file as its only argument.
