# Train authority

`/app/config/release-trains.json` lists release trains. The active train for a
seal is the open train (`status` exactly `open`) with the greatest `epoch`.
If multiple open trains share that epoch, pick the lexicographically smallest
`id`.

`/app/state/active-train.json` is a cached pointer written by prior migrates.
It must not override the open tip derived from `release-trains.json`.

`/app/config/archived-trains.json` is historical archaeology only.

Under the checked-in `/app/config/release-trains.json`, the open tip is
`train-east` at epoch `5`. Closing `train-east` leaves `train-west` at
epoch `4` as the open tip.
