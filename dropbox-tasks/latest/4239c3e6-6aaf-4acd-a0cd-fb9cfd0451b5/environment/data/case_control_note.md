# Case-control sampling and deployment calibration

The training rows are enriched: every subscribing contact was kept while
non-subscribers were down-sampled, so the training subscription rate is about one
half, far above the true live rate. The down-sampling was random within each class,
so within a class the feature distribution is unchanged (label shift only); only the
subscribe-to-not-subscribe mix differs between training and deployment.

There is no sampling-weight column and the deployment subscription rate is not given.
To produce scores that behave like true deployment probabilities — overall and within
each education group — you must recover the deployment subscription rate from the
unlabelled held-out contacts and reconcile your scores onto it. A model left at the
enriched training rate reads far too high and is badly miscalibrated within every
education group.
