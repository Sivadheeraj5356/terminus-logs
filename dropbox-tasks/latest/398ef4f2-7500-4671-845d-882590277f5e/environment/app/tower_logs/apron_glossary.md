apron terminology used across this task

actual inblock ts is the timestamp at which the aircraft physically reached the stand and the bridge could begin its connect or disconnect cycle. for departures it is the same field name even though the action is bridge undock.

basis points is one hundredths of a percent. eighteen hundred basis points means an eighteen percent uplift over the base.

body code is a short marker for the airframe class. only NB, WB, and RJ are accepted in the feebook.

cap breach is the first cycle whose addition to the cumulative billed cents for a carrier and gate zone in a month would push the running total strictly over the monthly cap. the breaching cycle still bills. the next cycle in the same key is the first one to be marked capped overage.

cycle id is a short opaque token unique to a single bridge cycle. follow up records can reuse the same cycle id to correct a prior posting.

effective_from is the inclusive lower bound of an airframe rate window. rates with a later effective_from supersede earlier ones once the moment arrives.

gate assigned ts is the timestamp at which ramp control posted the gate assignment. the assignment can precede the in block by many minutes, hours, or even days when an aircraft is diverted.

holdover is a status flag set by the duty controller when a bridge cycle is rebilled as a hold over from a previous turn that did not depart cleanly.

mtow tons is the maximum takeoff weight in metric tons recorded as a whole integer. floats are not part of the schema.

movement is ARR for arrival or DEP for departure. it does not affect the billed amount.

off hours window is bounded by start hhmm and end hhmm in feebook/offhours_window.toml. the start is exclusive at second precision and the end is inclusive.
