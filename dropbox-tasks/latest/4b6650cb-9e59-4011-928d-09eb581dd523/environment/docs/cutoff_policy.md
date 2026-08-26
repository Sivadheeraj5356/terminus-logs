# Journal inclusion cutoff

A journal is eligible when `rotate_gen <= bound_rotate + slack`.

Rebuild uses `bound_rotate` and `slack` from the profile manifest. Merge uses `bound_rotate` from the lexicographically last journal file in the profile fixture directory and `slack` from each journal header when evaluating that journal.
