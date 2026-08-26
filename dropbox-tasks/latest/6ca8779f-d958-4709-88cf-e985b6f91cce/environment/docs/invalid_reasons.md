# Invalid reasons

`OOB` — unit hex outside the map  
`BLOCKED` — unit starts on a blocked cell  
`OVERLAP` — two units share a starting hex  

When more than one applies, evaluate units in ascending `id` and prefer
`OOB`, then `BLOCKED`, then `OVERLAP`.
