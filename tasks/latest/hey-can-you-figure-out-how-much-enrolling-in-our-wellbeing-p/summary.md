# Hey, can you figure out how much enrolling in our wellbeing program changed peop

- **UUID:** `d68f981b-3bb6-4fb2-a036-8bcd67915105`
- **Slug:** `hey-can-you-figure-out-how-much-enrolling-in-our-wellbeing-p`
- **Category:** machine-learning
- **Difficulty:** hard

## Summary

Hey, can you figure out how much enrolling in our wellbeing program changed people's end of year wellbeing index? We ran a voluntary program last year, some staff joined and some did not, and I need the average effect of enrolling across everyone in these records, in wellbeing index units.

Enrollment was not random, people self selected and the program pushed some folks harder than others, so a plain comparison of enrolled versus not mostly picks up differences that were there before anyone joined. I want the causal effect of the program itself, averaged over the whole population in the data, not only those who enrolled.

## Harbor package

- [instruction.md](instruction.md) — full agent prompt
- [task.toml](task.toml) — Harbor metadata and timeouts
- [environment/](environment/) — Docker world / fixtures
- [solution/](solution/) — oracle solution
- [tests/](tests/) — verifier
