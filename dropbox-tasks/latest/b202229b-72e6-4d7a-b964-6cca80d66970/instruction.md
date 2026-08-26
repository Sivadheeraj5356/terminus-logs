You are given a stream of multi-station sensor events. Each event carries readings for a set of
features (one per station) plus a target. Stations come and go: a feature is out of schema when its cell
is empty, and can start reporting later. Run one online ridge (recursive least squares) regressor whose
dimension changes as features appear and disappear; report its predictions and retained state.

The model shares one precision matrix across the active features, so they are coupled: retiring one
changes the weights of the others. A newly reporting feature is added; one absent past a disclosed grace
window is retired; one that returns after retirement starts over, never resuming its old state.

Labels arrive late. A target seen with an event is that event's label, but only becomes available a
disclosed number of events later, so a labelled event folds in only when its label lands. A feature
retired while one of its readings still awaits a label forfeits that contribution. You predict before
folding anything at an event, and at each checkpoint read out the exact retained state.

All arithmetic is exact: readings scale to integers, state is integer, weights and predictions reduced
rationals matched exactly.

/app/docs/CONTRACT.md is the authoritative specification for processing order, timing, grace and
reinitialisation, arithmetic, and output format. Your solver /app/run.sh compiles and runs /app/Main.java
(JDK installed, no network). The starter builds but implements nothing; /app/data is a sample, graded
like the hidden streams, so do not special-case it.
