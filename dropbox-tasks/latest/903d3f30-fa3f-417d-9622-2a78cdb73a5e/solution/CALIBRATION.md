# Tidevault calibration record

This is the integration ledger for the frozen Tidevault rules, canonical action order, native hash, feature definitions, and deterministic search semantics. Tidevault has three rings (`I`, `M`, `O`), six sectors (`A` through `F`), eighteen fixed plies, three stones of each power per color, and scoring tides after plies 9 and 18. Placement occurs before rotation; clockwise maps A to B and counterclockwise maps A to F. None of the evidence below changes those rules.

## Design probes

The original 6/12/18 tide cadence was rejected before training because Violet closed all three scoring windows. Tide-aware mirror play won 2,000/2,000 games as Violet, pure teacher self-play won 100/100 as Violet, and an equal-budget learned screen returned nineteen Violet wins and one draw. The 9/18 cadence gives each color one closing move; a pre-freeze mirror probe returned 53 Gold wins, 62 Violet wins, and 85 draws in 200 games.

The retained baseline probe used seed 20260720. Uniform random play over 50,000 games returned 26,525 Gold wins, 10,934 draws, and 12,541 Violet wins. Tide-aware greedy versus random returned 1,947/51/2; random versus greedy returned 33/125/1,842. Greedy mirror play over 2,000 games returned 560 Gold wins, 832 draws, and 608 Violet wins with mean scores 4.618–4.671 and mean absolute margin 0.706. The complete timing-free log SHA-256 is `829be0e866904416710d6f81bf1ca41c98c439609989ea0551d33f06fa517c2c`.

## Reproducible training and screening

Seed 20260720 produced 1,200 complete games and 21,600 labeled decisions: 657 Gold wins, 288 draws, and 255 Violet wins. The shared dataset SHA-256 is `68966f73c2edf89eca9a518eecca844c9c5d5ab308b584cf1c3a43a42db5d074`; the retained training-log SHA-256 is `5b23a0e585e046756693674793c129b220a96a00d2c69afd70e7c1974ab0281c`. A second clean 1,200-game run from the current sources reproduced the dataset digest, log, and all five checkpoint files byte-for-byte in 65.54 seconds wall time.

All five checkpoints were screened at 256 nodes, width 16, depth 18, with one game in each color against every other checkpoint. Aggregate W/D/L results were e1 3/2/3, e2 3/2/3, e4 2/2/4, e8 4/3/1, and e16 3/1/4. The timing-free screen payload SHA-256 is `5a524353b567a3c9bf3001c13c68c75c5b360d755cc3eea2c5c989bdf0b71e63`. In the direct e1/e4 pair, e1 scored one win and one draw. A separate e8/e4 screen at 512 nodes and four games per color returned four e8 wins, three e4 wins, and one draw, but every decisive result followed the Gold seat; its payload SHA-256 is `df200229a722a2c09e0b3c1f9c49ab32a446bafb36c248b99a241c843b3c2df3`.

## Frozen tuples

| Role | Model ID | SHA-256 | Dataset SHA-256 | Nodes | Width | Depth | Seed |
| --- | --- | --- | --- | ---: | ---: | ---: | ---: |
| Runtime Violet | `tidevault-linear-s20260720-e0004` | `68920ae99a568aa74a85c1af3256c06b6590a95643792bcf00e11820dd519f0b` | `68966f73c2edf89eca9a518eecca844c9c5d5ab308b584cf1c3a43a42db5d074` | 4,096 | 24 | 18 | 20260720 |
| Strong Gold reference | `tidevault-linear-s20260720-e0001` | `588cc9dd43cac20ebf622d3547f4e677e187d66cb4138be1dcea43090773931e` | same corpus | 12,000 | 16 | 18 | 2026072002 |

Both use deterministic `beam-rank-lapse-v1`, root temperature zero, and rank lapse zero. A direct full-horizon integration match produced a genuine 5–4 Gold win with native hash `c0579404761c80fdaa9f15f3876219f4e3c3cae039154ebd6b5bc64d0af14603`. Strong-search mean/maximum latency was 1,791.853/4,115.848 ms and runtime-search mean/maximum latency was 438.260/1,001.062 ms.

The visible tide-aware Gold proxy was swept against e4 at width 24 and depth 18. At 512 nodes it scored 6 wins, 2 draws, and 0 losses; at each of 1,024, 2,048, and 4,096 nodes it scored 1 win, 3 draws, and 4 losses. At 8,192 nodes the four-game panel returned 0/2/2. The 4,096-node release point therefore preserves a measured 1/8 proxy win rate while avoiding the clearly easy 512-node setting. The complete e4 sweep payload SHA-256 is `ce41f82f6a33611f52d51b0e64556c42d7e273b0328623e0d268ed9a0972096e`; the retained log-file SHA-256 is `16112f419ff0df04966e5f7e270ab5b84f5c569b12e607f362fa0f27c5e5fb9d`.

## Release gate

The final digest `sha256:ebe11bf7d991bd387037f5ac9fec80995c6eda39303267997ee44f4842c1fc56` image was run with no network, 2 CPUs, and 3,072 MiB. The reference won 3/3 through `/app/arena` as participant UID 65534. Every game ended in a genuine 5–4 Gold board win at ply 18 with native hash `c0579404761c80fdaa9f15f3876219f4e3c3cae039154ebd6b5bc64d0af14603`, transcript SHA-256 `abe537eaf622a0bb7f5d2f0baf5c401aa24b220da44af6140182837c6dbc6f92`, and zero postgame participant requests. All 17 named tests passed and reward was one after each game. CTRF SHA-256 values were `59b52b8b88eb6f1f74d4d9c146873c71a57ae53da1ce18ba94433bdbb504cfbc`, `07440f210b50a4b10fc68ed0a48d2d64cfe56e63701b1f80e7999732296c67d7`, and `7ca9166926d2651885c90c9c6d53eaad5abda01a4c4812dcaf4d3e9300544a63`.

Fresh untouched, explicit-resignation, and completed Violet-win controls each received reward zero. Resignation and completed loss each passed 16/17 structural tests and failed only the genuine-Gold-win requirement; the completed loss was Violet 6–4 at ply 18 with zero postgame requests. The untouched opening passed 14/17 and failed the terminal, postgame-terminal, and genuine-win requirements. The retained release-gate log SHA-256 is `40db09e093dd6a8174c6ec3b4ba148a216ed32083d1ce25a4d796b3d2634ae5d`.

Difficulty remains a best local estimate until clean frontier-provider trials are available. Provider failures or zero-token trials are recorded separately and never converted into gameplay losses; an unfinished valid trial is not silently excluded. The intended release band is Medium, and future basket evidence may tune only the disclosed checkpoint and deterministic search controls without changing game rules or verifier semantics.
