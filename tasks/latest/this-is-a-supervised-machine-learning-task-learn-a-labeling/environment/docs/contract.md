# Task and interface contract

This is a supervised machine-learning task. A hidden labeling rule, fixed within an instance, assigns a 0 or 1 label to each example from its features and the examples before it. The rule is learned from the labeled training examples and used to predict the labels of the unlabeled test examples.

## Data

An instance is a directory with two files. train.csv holds the labeled training examples, with the header `event_id,f0,f1,f2,f3,label` followed by rows in sequence order, where each fj is a small nonnegative integer and label is 0 or 1. test.csv holds the unlabeled examples, with the header `event_id,f0,f1,f2,f3` and its own rows in sequence order, without a label column.

The trained model runs as `solver <instance_dir>` and writes exactly one JSON document to standard output, of the form `{"predictions": [<label>, <label>, ...]}`, with one 0 or 1 label per test.csv example in row order.

## What is guaranteed

The same hidden rule labels both the training and test examples within one instance. The rule depends on the current example's features together with a bounded amount of information carried from earlier examples in the same sequence, so order matters and the examples are not independent; not every feature necessarily participates.

The carried information is small and integer-valued: it behaves like a single running counter that accumulates along the sequence and falls back to zero once it reaches a hidden bound. How that counter drives the label, how far back the state that decides a label is read from, which features take part, and the bound itself are the hidden per-instance parameters. Because this state is small and the parameters lie in a modest range, the rule is identifiable from the training examples: the parameters that reproduce every training label also reproduce every held-out test label, as the contract guarantees. Each instance uses its own hidden parameters, so the model is learned separately from each instance's own training examples. Each sequence carries its state from its own first row, so the test sequence is labeled on its own, independently of the training sequence.

## Scoring

Each instance is scored by comparing the predicted labels to the hidden test labels, and a model must match at least 99 percent of the test examples. All graded instances are held out; a learned model can be checked by confirming it reproduces the labels of its own training examples. The worked public instance under `/app/environment/data` additionally ships `test_labels.csv`, the true labels of its own `test.csv`, so a candidate can score a recovered rule end to end on that instance before submitting. A model that memorizes the training examples, or that ignores the sequence, does not generalize and scores poorly.
