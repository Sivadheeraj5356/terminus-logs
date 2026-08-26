# Background: hidden Markov models, dwell times, and numerical stability

This note is general background on hidden Markov models and the inference problem. It is context, not an implementation guide; the binding requirements are in `hmm-spec.md`.

## Hidden Markov models

A hidden Markov model describes a system that moves between a finite set of hidden states according to a Markov chain, emitting an observable symbol at each step from a distribution that depends on the current state. The model is specified by an initial state distribution, a state-to-state transition matrix, and, for discrete observations, a state-to-symbol emission matrix. HMMs are a staple of sequence modelling — speech recognition, part-of-speech tagging, gene finding, and time-series segmentation all use them — because they combine a tractable latent structure with efficient exact inference.

## The three classical problems

Rabiner's tutorial frames HMM work as three problems. The **evaluation** problem asks for the likelihood of an observation sequence under a model, P(O | lambda). The **decoding** problem asks for the most likely hidden state sequence (the Viterbi path). The **learning** problem asks for the parameters that maximise the likelihood of the data, solved by the Baum-Welch algorithm, an expectation-maximisation procedure. The forward algorithm solves evaluation with a dynamic program that accumulates the joint probability of the observations so far and the current state; running the same idea from the end of the sequence gives the backward variable, and combining the two at a timestep gives the smoothed posterior over states at that step given the entire sequence — the quantity the Baum-Welch E-step consumes.

## Dwell times

An ordinary HMM makes a strong structural assumption that is easy to miss: because the chain re-rolls the transition matrix at every step, the number of consecutive steps spent in a state is geometrically distributed, with the most probable dwell always being a single step. Many real processes — phonemes in speech, rainfall regimes, machine-condition states, sleep stages — have dwell times that look nothing like geometric: they concentrate around a typical length, or have a hard minimum. The literature therefore developed duration-explicit variants, sometimes called explicit-duration, variable-duration, or hidden semi-Markov models, in which each state carries its own dwell-time distribution and the memoryless-transition assumption is dropped. Ferguson's 1980 formulation and Yu's 2010 survey are the standard references. Exact inference for these models is still polynomial, but the textbook HMM recurrences do not apply as-is, and results in the literature are reported with careful attention to how sequence boundaries interact with incomplete dwells.

## Scaling and log space

Forward and backward quantities shrink geometrically with sequence length: each step multiplies by probabilities below one, so for long sequences the values fall below the smallest representable double and underflow to zero. Naively multiplying raw probabilities therefore destroys the computation on sequences of more than a few hundred steps, depending on the model. Two standard remedies exist. The first rescales the running quantities at each step by a per-step normaliser and accumulates the logs of the normalisers to recover the log-likelihood. The second carries every quantity as its logarithm from the start and replaces each sum of probabilities with a log-sum-exp, the numerically stable evaluation of `log(sum_i exp(x_i))` that factors out the largest term before exponentiating. The log-space formulation is the more robust of the two and is the usual choice when the same code must handle very long sequences and very small probabilities.

## Further reading

- L. R. Rabiner, "A tutorial on hidden Markov models and selected applications in speech recognition", Proceedings of the IEEE 77(2), 257-286 (1989).
- J. D. Ferguson, "Variable duration models for speech", Proc. Symposium on the Application of Hidden Markov Models to Text and Speech, 143-179 (1980).
- S.-Z. Yu, "Hidden semi-Markov models", Artificial Intelligence 174(2), 215-243 (2010).
- C. M. Bishop, "Pattern Recognition and Machine Learning", ch. 13, Springer (2006).
