#!/usr/bin/env bash
set -euo pipefail

mkdir -p /app/task_file/models
cat > /app/task_file/models/shelter_staging.mzn <<'MZN'
int: P; int: W; int: Z; int: T; int: H;
array[1..P] of int: pallet_count;
array[1..P] of int: protection;
array[1..P] of bool: mandatory;
array[1..P] of 1..H: handling_class;
array[1..P] of int: arrival_minute;
array[1..P] of int: process_minutes;
array[1..P] of int: deadline_minute;
array[1..P,1..Z] of bool: zone_allowed;
array[1..P,1..T] of bool: team_allowed;
array[1..W] of int: wave_capacity;
array[1..Z] of int: zone_capacity;
array[1..T] of int: team_capacity;
array[1..P] of 0..P: parent;
int: C;
array[1..C] of 1..P: conflict_a;
array[1..C] of 1..P: conflict_b;
int: min_scheduled; int: max_scheduled; int: min_cells;
array[1..H,1..H] of int: class_changeover;
array[1..H] of int: class_min_waves;
array[1..T] of int: team_wave_limit;

array[1..P] of var 0..W: wave;
array[1..P] of var 0..Z: zone;
array[1..P] of var 0..T: team;
array[1..P] of var bool: scheduled;
array[1..W,1..T] of var bool: cell_used;
array[1..W] of var bool: wave_used;
array[1..W] of var 0..H: wave_class;
array[1..W,1..T] of var bool: team_wave_used;
array[1..W] of var 0..1000000: wave_start;
array[1..W] of var 0..1000000: wave_duration;
array[1..W] of var 0..1000000: wave_finish;

constraint forall(p in 1..P)(scheduled[p] <-> wave[p] > 0);
constraint forall(p in 1..P)(scheduled[p] <-> zone[p] > 0);
constraint forall(p in 1..P)(scheduled[p] <-> team[p] > 0);
constraint forall(p in 1..P where mandatory[p])(scheduled[p]);
constraint forall(p in 1..P, z in 1..Z)(bool2int(zone[p] = z) <= bool2int(zone_allowed[p,z]));
constraint forall(p in 1..P, t in 1..T)(bool2int(team[p] = t) <= bool2int(team_allowed[p,t]));
constraint sum(p in 1..P)(bool2int(scheduled[p])) >= min_scheduled;
constraint sum(p in 1..P)(bool2int(scheduled[p])) <= max_scheduled;
constraint forall(w in 1..W)(sum(p in 1..P)(pallet_count[p] * bool2int(wave[p] = w)) <= wave_capacity[w]);
constraint forall(z in 1..Z)(sum(p in 1..P)(pallet_count[p] * bool2int(zone[p] = z)) <= zone_capacity[z]);
constraint forall(t in 1..T)(sum(p in 1..P)(pallet_count[p] * bool2int(team[p] = t)) <= team_capacity[t]);
constraint forall(p in 1..P where parent[p] > 0)(scheduled[p] -> (scheduled[parent[p]] /\ wave[parent[p]] <= wave[p]));
constraint forall(c in 1..C)((scheduled[conflict_a[c]] /\ scheduled[conflict_b[c]]) -> wave[conflict_a[c]] != wave[conflict_b[c]]);
constraint forall(w in 1..W, t in 1..T)(cell_used[w,t] <-> exists(p in 1..P)(wave[p] = w /\ team[p] = t));
constraint sum(w in 1..W, t in 1..T)(bool2int(cell_used[w,t])) >= min_cells;
constraint forall(w in 1..W)(wave_used[w] <-> exists(p in 1..P)(wave[p] = w));
constraint wave_used[1];
constraint forall(w in 2..W)(wave_used[w] -> wave_used[w-1]);
constraint forall(w in 1..W)((wave_class[w] = 0) <-> not wave_used[w]);
constraint forall(p in 1..P)(scheduled[p] -> wave_class[wave[p]] = handling_class[p]);
constraint forall(h in 1..H)(sum(w in 1..W)(bool2int(wave_class[w] = h)) >= class_min_waves[h]);
constraint forall(w in 1..W, t in 1..T)(team_wave_used[w,t] <-> exists(p in 1..P)(wave[p] = w /\ team[p] = t));
constraint forall(t in 1..T)(sum(w in 1..W)(bool2int(team_wave_used[w,t])) <= team_wave_limit[t]);
constraint forall(w in 1..W)(wave_duration[w] = max(p in 1..P)(process_minutes[p] * bool2int(wave[p] = w)));
constraint wave_start[1] >= class_changeover[wave_class[1],wave_class[1]];
constraint forall(w in 2..W)(wave_used[w] -> wave_start[w] >= wave_finish[w-1] + class_changeover[wave_class[w-1],wave_class[w]]);
constraint forall(w in 1..W, p in 1..P)(wave[p] = w -> wave_start[w] >= arrival_minute[p]);
constraint forall(w in 1..W)(if wave_used[w] then wave_finish[w] = wave_start[w] + wave_duration[w] else wave_start[w] = 0 /\ wave_finish[w] = 0 endif);
constraint forall(p in 1..P)(scheduled[p] -> wave_finish[wave[p]] <= deadline_minute[p]);

var int: scheduled_count = sum(p in 1..P)(bool2int(scheduled[p]));
var int: setup_total = class_changeover[wave_class[1],wave_class[1]] + sum(w in 2..W)(if wave_used[w] then class_changeover[wave_class[w-1],wave_class[w]] else 0 endif);
var int: makespan = max(w in 1..W)(wave_finish[w]);
var int: objective = 1000000 * sum(p in 1..P)(protection[p] * bool2int(scheduled[p])) + 10000 * scheduled_count - 100 * setup_total - makespan - sum(p in 1..P)(wave[p]);
solve maximize objective;
output ["RESULT ", show(wave), "|", show(zone), "|", show(team), "|", show(objective), "\n"];
MZN
