# Condition, Assert, and Outcome Rules

Clause namespace: `PREDICATE-*`

## PREDICATE-1 Supported predicates

Evaluate only captured-fact predicates:

- `ConditionPathExists=` / `AssertPathExists=`
- `ConditionPathIsDirectory=` / `AssertPathIsDirectory=`
- `ConditionPathIsMountPoint=` / `AssertPathIsMountPoint=`
- `ConditionKernelCommandLine=` / `AssertKernelCommandLine=`
- `ConditionArchitecture=` / `AssertArchitecture=`
- `ConditionVirtualization=` / `AssertVirtualization=`
- `ConditionFirmware=` / `AssertFirmware=`
- `ConditionHost=` / `AssertHost=`
- `ConditionFirstBoot=` / `AssertFirstBoot=`

Unary `|` negation prefixes invert a single predicate. Trigger groups follow the capsule: all conditions in a unit form one conjunctive group unless a documented OR-group marker is present (this closed model uses conjunctive groups only).

## PREDICATE-2 Skip versus fail

A false condition skips its unit without marking the unit failed. A false assertion fails the unit. Dependent-job propagation, public reason codes, and `boot.trace` must preserve that difference: skipped peers use reason `condition-failed`; assertion failures use `assert-failed`.

## PREDICATE-3 Evaluation timing

Evaluate predicates after effective-fragment construction and specifier expansion, against the fixed captured facts and device/path tables. Do not re-read evaluator environment variables or mutate facts during simulation.

## PREDICATE-4 Job states

Simulate jobs through: `queued`, `waiting`, `ready`, `started`, `skipped`, `failed`, `stopped`, `excluded`. Honor ordering predecessors, active initial units from `runtime.facts`, stop jobs, device/mount readiness, target completion, and dependency outcomes.

## PREDICATE-5 Service outcomes

The simulator does not run `Exec*` commands. Declared service outcomes in `runtime.facts` as `service_outcome=<unit>\t<success|failure>` supply the bounded observable result when a service job reaches `ready`.

## PREDICATE-6 Acceptance matching

Match `acceptance.jobs` only after the complete cold transaction finishes. Extra visible jobs, missing expected jobs, incorrect public reasons, unresolved waiting jobs, or a final target that cannot complete reject the order.

## PREDICATE-7 Public reasons

Canonical public reasons include: `started`, `condition-failed`, `assert-failed`, `dependency-failed`, `device-absent`, `conflict-stop`, `excluded-cycle`, `requisite-inactive`, `skipped-ignore`.

## PREDICATE-8 Omissions

This closed model omits `ConditionACPower`, capability checks, security module checks, and directory-not-empty predicates.
