# Output schema

Write the result to `/app/estimate.json` as a single JSON object.

Required field:

- `estimate`: the point estimate of the population average treatment effect of
  enrollment on the wellbeing index, as a finite JSON number in the units of
  `wellbeing_index`.

Only the `estimate` field is read by the grader. You may add any other fields you
find useful (for example notes on your adjustment set or method); they are
ignored.

Example shape:

    {"estimate": 0.0}

The value above is a placeholder for shape only and is not a correct answer.
